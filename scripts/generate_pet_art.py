# coding: utf-8
"""ConfigPilot 桌宠立绘生成流水线(调度 OpenAI 兼容的 images/generations 接口)。

一次调用产出「透明底 / 已裁边 / 已缩放」的桌宠 PNG,可直接被
qml/pet/PetSprite.qml 的 imagePath 通道加载。

密钥与接口地址只从环境变量读取,代码里不出现任何具体站点或密钥:
    RELYX_API_BASE   形如 https://<host>/v1
    RELYX_API_KEY    sk-...

常用命令(仓库根目录,使用 .venv 的 python):
    # 1) 验证密钥是否可用
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --ping
    # 2) 出图(默认 navigator 概念 + gpt-image-2.5)
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --style navigator --models gpt-image-2.5
    # 3) 三个概念各出一张横向对比
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --style all --models gpt-image-2.5
    # 4) 同一概念在四个模型上各出一张,挑画风
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --style navigator ^
        --models gpt-image-2,gpt-image-2.5,gpt-image-2.5-flare,gpt-image-2.5-sunburst
    # 5) 选定后装进 resources/pet/ 并写入桌宠配置
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --install .artifacts\\pet\\navigator__gpt-image-2.5__01.png --pet-name navigator
    # 6) 离线自检(合成假立绘跑完抠底/裁边/缩放/预览链路)
    .venv\\Scripts\\python.exe scripts\\generate_pet_art.py --self-test

图像处理只用项目已有依赖 PySide6 的 QImage,不引入 Pillow/numpy。
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / ".artifacts" / "pet"
DEFAULT_MODELS = ("gpt-image-2.5",)
DEFAULT_SIZE = "1024x1024"
DEFAULT_FINAL_SIZE = 512

# ---------------------------------------------------------------- 角色设定
# 通用画风:Q版二头身、粗等宽描线、平涂、贴纸感 —— 与 DeepSeek Harness 桌宠同一档
# 观感,但形体全部走下面的概念块,不复用「鲸鱼娘」的任何元素。
STYLE_CORE = (
    "chibi Q-version anime mascot sticker, two-heads-tall proportion, oversized head, "
    "tiny body, front-facing three-quarter standing pose, full body visible, "
    "kawaii rounded shapes, thick even-weight warm dark-brown line art, flat cel shading "
    "with one soft gradient, large glossy anime eyes with two white highlights, "
    "tiny dot blush, small simple smiling mouth, "
    "clean crisp silhouette that stays readable when scaled down to 120 pixels, "
    "fully transparent background, character only, centered with even margin, "
    "no ground shadow, no text, no letters, no watermark, no logo, no border, no scenery"
)

# 鲸鱼娘元素排除清单:蓝发 + 女仆头饰 + 鲸鱼尾 + 深蓝领结 + 领口菱形宝石。
AVOID = (
    "strictly avoid: maid headdress, frilled headband, cat-ear headband, "
    "blue or periwinkle or silver-blue or lavender hair, whale, dolphin, fish, fin, "
    "tail, gills, sea creature motifs, ocean waves, anchor, sailor collar, "
    "navy bow tie, diamond gem brooch at the collar, droopy half-closed sleepy eyes, "
    "overall blue-purple color scheme"
)

STYLES: dict[str, dict[str, str]] = {
    "navigator": {
        "label": "小领航 · 阿诺(ConfigPilot 领航员)",
        "brief": (
            "a sweet little navigator girl with warm apricot-orange short hair, soft outward "
            "hair flips and one thin side braid, honey-teal eyes, a small cream aviator cap "
            "with a brass pin, a cream short capelet with teal trim and brass buttons, "
            "a warm brown belt holding a tiny brass compass charm and a golden key charm, "
            "hugging one large golden coin with a star engraving; "
            "color palette: apricot, cream white, teal, brass gold"
        ),
    },
    "barista": {
        "label": "小焙 · 玛琪(烘焙记账师)",
        "brief": (
            "a cozy little barista girl with milk-tea brown hair in a low bun pinned by a "
            "cinnamon stick, warm amber eyes, a soft chocolate beret, a rust-colored dress "
            "under a cream apron with a pocket full of receipts, holding a tiny latte cup "
            "topped by a coin-shaped cookie, a small brass weighing scale at her side; "
            "color palette: caramel, cream, rust, olive green"
        ),
    },
    "archivist": {
        "label": "小档 · 璃(档案管理员)",
        "brief": (
            "a tidy little archivist girl with soft rose-pink bob hair and one white streak, "
            "sage-green eyes behind round gold-rim glasses, an oversized cream sweater with "
            "rolled cuffs, a rose-gold paperclip hairpin, hugging a ledger book sealed with "
            "wax, a small brass key dangling from her sleeve; "
            "color palette: rose pink, cream, sage green, gold"
        ),
    },
}


def build_prompt(style: str) -> str:
    """拼出一次生成用的完整提示词。"""
    return f"{STYLES[style]['brief']}, {STYLE_CORE}. {AVOID}."


# ---------------------------------------------------------------- HTTP 调用
def api_base() -> str:
    base = os.environ.get("RELYX_API_BASE", "").strip().rstrip("/")
    if not base:
        raise SystemExit("缺少 RELYX_API_BASE 环境变量(形如 https://<host>/v1)")
    return base


def api_key() -> str:
    key = os.environ.get("RELYX_API_KEY", "").strip()
    if not key:
        raise SystemExit("缺少 RELYX_API_KEY 环境变量")
    return key


def _request(url: str, payload: dict | None, key: str, timeout: int) -> tuple[int, bytes]:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"接口不可达: {url} -> {exc.reason}") from exc


def ping() -> int:
    """只验证密钥是否可用,顺带列出支持 image 的模型。"""
    key = api_key()
    status, body = _request(f"{api_base()}/models", None, key, 30)
    if status != 200:
        print(f"[FAIL] HTTP {status}: {body.decode('utf-8', 'replace')[:400]}")
        return 1
    try:
        ids = sorted(str(item.get("id", "?")) for item in json.loads(body).get("data", []))
    except (ValueError, AttributeError, TypeError):
        ids = []
    print(f"[OK] 密钥可用,共 {len(ids)} 个模型")
    for item in ids:
        if "image" in item.lower():
            print(f"  image -> {item}")
    return 0


def _param_profiles(model: str, prompt: str, count: int, size: str,
                    quality: str) -> list[dict]:
    """不同中转站对可选参数支持不一,按宽容度逐级降级。"""
    base = {"model": model, "prompt": prompt, "n": count, "size": size}
    if quality:
        base["quality"] = quality
    profiles = [
        dict(base, background="transparent", output_format="png"),
        dict(base, background="transparent", response_format="b64_json"),
        dict(base, output_format="png"),
        dict(base, response_format="b64_json"),
        dict(base),
    ]
    if not quality:
        profiles = [{k: v for k, v in p.items() if k != "quality"} for p in profiles]
    return profiles


def generate(model: str, prompt: str, count: int, size: str, quality: str,
             timeout: int) -> list[bytes]:
    """调用 images/generations,返回 PNG 字节列表。"""
    key = api_key()
    url = f"{api_base()}/images/generations"
    last_error = "无可用参数组合"
    for profile in _param_profiles(model, prompt, count, size, quality):
        status, body = _request(url, profile, key, timeout)
        if status == 200:
            try:
                payload = json.loads(body)
            except ValueError:
                last_error = f"响应不是 JSON: {body[:200]!r}"
                continue
            blobs = [_decode_item(item, key, timeout) for item in (payload.get("data") or [])]
            blobs = [blob for blob in blobs if blob]
            if blobs:
                extras = sorted(set(profile) - {"model", "prompt", "n", "size"})
                print(f"  [OK] {model} 生效参数集 {extras}")
                return blobs
            last_error = f"响应无图片数据: {json.dumps(payload, ensure_ascii=False)[:300]}"
        else:
            last_error = f"HTTP {status}: {body.decode('utf-8', 'replace')[:300]}"
        if status in (401, 403):  # 鉴权问题降级重试没有意义
            break
    raise RuntimeError(f"{model} 生成失败 -> {last_error}")


def _decode_item(item: dict, key: str, timeout: int) -> bytes | None:
    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        if b64.lstrip().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        return base64.b64decode(b64)
    link = item.get("url") or item.get("image_url")
    if isinstance(link, str) and link.startswith("http"):
        request = urllib.request.Request(link, headers={"Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"  [WARN] 图片下载失败 {link} -> {exc}", file=sys.stderr)
    return None


# ---------------------------------------------------------------- 图像处理
# QImage.Format_ARGB32 在 Windows(小端)上的字节序是 B, G, R, A。
def _qt_image_class():
    try:
        from PySide6.QtGui import QImage
    except ImportError as exc:  # pragma: no cover - 取决于运行环境
        raise SystemExit("需要 PySide6(项目 .venv 已装): " + exc) from exc
    return QImage


def _buffer(image):
    """返回 (可写内存视图, 行跨距)。"""
    return memoryview(image.bits()).cast("B"), image.bytesPerLine()


def remove_solid_background(image, tolerance: int = 44) -> int:
    """四边洪水填充抠掉单一背景色(接口没给透明底时的兜底),返回抠掉的像素数。"""
    width, height = image.width(), image.height()
    view, bpl = _buffer(image)

    def rgb(x: int, y: int) -> tuple[int, int, int]:
        o = y * bpl + x * 4
        return view[o], view[o + 1], view[o + 2]

    corners = [rgb(0, 0), rgb(width - 1, 0), rgb(0, height - 1), rgb(width - 1, height - 1)]
    base = corners[0]
    spread = max(max(abs(c[i] - base[i]) for i in range(3)) for c in corners)
    if spread > tolerance:
        return 0  # 背景不单一(多半已带 alpha),不插手

    # 0=未定 1=背景 2=前景但贴边
    flags = bytearray(width * height)
    queue = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(1, height - 1):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        idx = y * width + x
        if flags[idx]:
            continue
        o = y * bpl + x * 4
        if (abs(view[o] - base[0]) > tolerance or abs(view[o + 1] - base[1]) > tolerance
                or abs(view[o + 2] - base[2]) > tolerance):
            flags[idx] = 2
            continue
        flags[idx] = 1
        view[o + 3] = 0
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    # 贴着抠除区的前景像素给半透明,缩到 120px 时不留白边锯齿
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if flags[idx] != 2:
                continue
            if (flags[idx - 1] == 1 if x > 0 else False) \
                    or (flags[idx + 1] == 1 if x + 1 < width else False) \
                    or (flags[idx - width] == 1 if y > 0 else False) \
                    or (flags[idx + width] == 1 if y + 1 < height else False):
                view[y * bpl + x * 4 + 3] = 150
    return flags.count(1)


def has_real_transparency(image) -> bool:
    """是否存在真正的透明像素。

    接口经常返回「带 alpha 通道但整幅全不透明」的 PNG,只看 hasAlphaChannel()
    会误判成已透明,从而跳过抠底。
    """
    view, bpl = _buffer(image)
    width, height = image.width(), image.height()
    if bpl == width * 4:
        return min(bytes(view[3::4])) < 255
    for y in range(height):
        if min(bytes(view[y * bpl + 3:y * bpl + width * 4:4])) < 255:
            return True
    return False


def alpha_bbox(image, threshold: int = 8):
    """不透明区域包围盒 (x, y, w, h);全透明返回 None。"""
    width, height = image.width(), image.height()
    view, bpl = _buffer(image)
    min_x, max_x, min_y, max_y = width, -1, height, -1
    for y in range(height):
        row_alpha = view[y * bpl + 3::4]
        hit = False
        for x in range(width):
            if row_alpha[x] > threshold:
                hit = True
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
        if hit:
            if y < min_y:
                min_y = y
            max_y = y
    if max_x < 0:
        return None
    return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1


def _paste(dst_image: "object", src_image: "object", x: int, y: int) -> None:
    """把 src 的原始 BGRA 像素块拷进 dst(不做混合,用于摆放已带 alpha 的图层)。"""
    src_view, src_bpl = _buffer(src_image)
    dst_view, dst_bpl = _buffer(dst_image)
    span = src_image.width() * 4
    payload = bytes(src_view[: src_bpl * src_image.height()])
    for row in range(src_image.height()):
        start = (y + row) * dst_bpl + x * 4
        dst_view[start:start + span] = payload[row * src_bpl:row * src_bpl + span]


def finalize(raw: bytes, out_path: Path, final_size: int, margin_ratio: float) -> dict:
    """解码 -> 抠底 -> 裁边 -> 补方留白 -> 缩放 -> 存 PNG,返回统计信息。"""
    QImage = _qt_image_class()
    image = QImage.fromData(raw, "PNG")
    if image.isNull():
        image = QImage.fromData(raw)
    if image.isNull():
        raise RuntimeError("返回内容不是可解码的 PNG")
    # 先统一成 4 字节 BGRA 布局,再判断透明度,避免索引色/16 位格式误读缓冲。
    image = image.convertToFormat(QImage.Format_ARGB32)
    had_alpha = has_real_transparency(image)
    removed = 0 if had_alpha else remove_solid_background(image)
    box = alpha_bbox(image)
    if box:
        image = image.copy(*box)
    side = max(image.width(), image.height())
    pad = max(1, int(side * margin_ratio))
    canvas = QImage(side + 2 * pad, side + 2 * pad, QImage.Format_ARGB32)
    canvas.fill(0x00000000)
    _paste(canvas, image, (canvas.width() - image.width()) // 2,
           (canvas.height() - image.height()) // 2)
    canvas = canvas.scaled(final_size, final_size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(out_path), "PNG"):
        raise RuntimeError(f"PNG 写入失败: {out_path}")
    return {
        "trimmed": (0, 0) if box is None else (box[2], box[3]),
        "out": (canvas.width(), canvas.height()),
        "had_alpha": had_alpha,
        "removed_px": removed,
        "bytes": out_path.stat().st_size,
    }


def write_preview(image_path: Path, preview_path: Path, size: int = 256) -> None:
    """把立绘分别叠到浅色/深色底,判断 120px 桌宠尺寸下的可读性。"""
    QImage = _qt_image_class()
    sprite = QImage(str(image_path))
    if sprite.isNull():
        return
    sprite = sprite.scaled(size, size).convertToFormat(QImage.Format_ARGB32)
    gap = 16
    canvas_w = size * 2 + gap
    light = bytes([0xEF, 0xE8, 0xE6, 0xFF])          # BGRA 浅灰
    dark = bytes([0x3A, 0x2F, 0x2A, 0xFF])           # BGRA 深灰
    canvas = QImage(canvas_w, size, QImage.Format_ARGB32)
    view, bpl = _buffer(canvas)
    row = light * size + bytes([0x80, 0x80, 0x80, 0xFF]) * gap + dark * size
    for y in range(size):
        view[y * bpl:(y + 1) * bpl] = row
    src_view, src_bpl = _buffer(sprite)
    pixels = bytes(src_view[: src_bpl * size])
    for y in range(size):
        for x in range(size):
            so = y * src_bpl + x * 4
            alpha = pixels[so + 3]
            if alpha == 0:
                continue
            for offset in (0, size + gap):
                o = y * bpl + (x + offset) * 4
                for channel in range(3):
                    view[o + channel] = (pixels[so + channel] * alpha
                                         + view[o + channel] * (255 - alpha)) // 255
                view[o + 3] = 0xFF
    canvas.save(str(preview_path), "PNG")


# ---------------------------------------------------------------- 安装
def install(artifact: Path, pet_name: str, update_config: bool) -> int:
    """把定稿立绘放进 resources/pet/,并可选写入桌宠配置的 pet_image。"""
    if not artifact.is_file():
        raise SystemExit(f"找不到立绘文件: {artifact}")
    target_dir = REPO_ROOT / "resources" / "pet"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{pet_name}.png"
    shutil.copyfile(artifact, target)
    print(f"[OK] 立绘已就位: {target.relative_to(REPO_ROOT)}")
    if not update_config:
        return 0
    sys.path.insert(0, str(REPO_ROOT))
    from backend.pet_config import load_pet_config, resolve_pet_config_path, save_pet_config

    config_path = resolve_pet_config_path()
    config = load_pet_config(config_path)
    save_pet_config(config_path, dataclasses.replace(config, pet_image=str(target)))
    print(f"[OK] 桌宠形象已写入 {config_path}")
    return 0


# ---------------------------------------------------------------- 自检
def self_test(out_dir: Path) -> int:
    """不联网:合成两种输入(纯色背景 / 已带透明底),验证后处理全链路。"""
    QImage = _qt_image_class()
    size = 256
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(0xFFF2EFE9)  # 纯色背景(接口未给透明底时的形态)
    view, bpl = _buffer(image)
    for y in range(60, 210):  # 画一个不居中的"角色"块
        for x in range(90, 180):
            o = y * bpl + x * 4
            view[o], view[o + 1], view[o + 2], view[o + 3] = 0x3A, 0x5C, 0xC8, 0xFF
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "_selftest_raw.png"
    image.save(str(raw), "PNG")
    stats = finalize(raw.read_bytes(), out_dir / "_selftest_final.png", DEFAULT_FINAL_SIZE, 0.06)
    write_preview(out_dir / "_selftest_final.png", out_dir / "_selftest_preview.png")

    # 用例 B:接口已经给了真透明底 —— 必须原样保留 alpha,只做裁边,不再抠图。
    transparent = QImage(size, size, QImage.Format_ARGB32)
    transparent.fill(0x00000000)
    tview, tbpl = _buffer(transparent)
    for y in range(40, 200):
        for x in range(120, 220):
            o = y * tbpl + x * 4
            tview[o], tview[o + 1], tview[o + 2], tview[o + 3] = 0x20, 0xD0, 0xE8, 0xFF
    raw_t = out_dir / "_selftest_alpha_raw.png"
    transparent.save(str(raw_t), "PNG")
    stats_t = finalize(raw_t.read_bytes(), out_dir / "_selftest_alpha_final.png",
                       DEFAULT_FINAL_SIZE, 0.06)

    checks = {
        "纯色背景已抠除": stats["removed_px"] > 20000,
        "输出尺寸 512": stats["out"] == (DEFAULT_FINAL_SIZE, DEFAULT_FINAL_SIZE),
        "裁边生效(90x150)": stats["trimmed"] == (90, 150),
        "预览已生成": (out_dir / "_selftest_preview.png").is_file(),
        "透明底被识别": stats_t["had_alpha"] is True,
        "透明底未被二次抠图": stats_t["removed_px"] == 0,
        "透明底裁边(100x160)": stats_t["trimmed"] == (100, 160),
    }
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print(f"self-test solid={stats}")
    print(f"self-test alpha  ={stats_t}")
    return 0 if all(checks.values()) else 1


# ---------------------------------------------------------------- 入口
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 ConfigPilot 桌宠 Q版立绘")
    parser.add_argument("--style", default="navigator",
                        help="角色概念:" + "/".join(STYLES) + " 或 all")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS), help="逗号分隔的生图模型")
    parser.add_argument("--n", type=int, default=1, help="每个模型出几张")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="接口出图尺寸")
    parser.add_argument("--quality", default="high", help="接口画质参数,传空串则不下发")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="产物目录")
    parser.add_argument("--final-size", type=int, default=DEFAULT_FINAL_SIZE)
    parser.add_argument("--margin", type=float, default=0.06, help="裁边后四周留白比例")
    parser.add_argument("--keep-raw", action="store_true", help="保留接口原始大图")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--ping", action="store_true", help="只验证密钥")
    parser.add_argument("--dry-run", action="store_true", help="只打印请求,不联网")
    parser.add_argument("--self-test", action="store_true", help="离线验证后处理链路")
    parser.add_argument("--install", metavar="FILE", help="把指定立绘装进 resources/pet/")
    parser.add_argument("--pet-name", default="navigator")
    parser.add_argument("--no-config", action="store_true", help="安装时不改用户配置")
    parser.add_argument("--list-styles", action="store_true", help="打印角色概念")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)

    if args.list_styles:
        for name, spec in STYLES.items():
            print(f"{name}: {spec['label']}\n    {spec['brief']}")
        return 0
    if args.self_test:
        return self_test(out_dir)
    if args.install:
        return install(Path(args.install), args.pet_name, not args.no_config)
    if args.ping:
        return ping()

    if args.style != "all" and args.style not in STYLES:
        raise SystemExit(f"未知 --style {args.style},可选 {list(STYLES)} 或 all")
    styles = list(STYLES) if args.style == "all" else [args.style]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    failures = 0
    for style in styles:
        prompt = build_prompt(style)
        for model in models:
            if args.dry_run:
                print(json.dumps({"model": model, "size": args.size, "prompt": prompt},
                                 ensure_ascii=False, indent=2))
                continue
            print(f"[RUN] {style} x {model}")
            try:
                blobs = generate(model, prompt, args.n, args.size, args.quality, args.timeout)
            except RuntimeError as exc:
                print(f"[FAIL] {exc}", file=sys.stderr)
                failures += 1
                continue
            for index, blob in enumerate(blobs, start=1):
                stem = f"{style}__{model}__{index:02d}"
                if args.keep_raw:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / f"{stem}__raw.png").write_bytes(blob)
                final = out_dir / f"{stem}.png"
                stats = finalize(blob, final, args.final_size, args.margin)
                write_preview(final, out_dir / f"{stem}_preview.png", args.final_size)
                print(f"[OK] {final} out={stats['out']} alpha={stats['had_alpha']} "
                      f"抠底={stats['removed_px']} {stats['bytes']}B")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
