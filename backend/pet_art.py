# coding: utf-8
"""桌宠形象令牌 ↔ 立绘文件的解析。

内置立绘随程序目录走(``resources/pet/``),不依赖用户配置目录,所以打包后
换机器、换用户名都不会失效;用户配置里只保存一个短令牌。

``pet_image`` 配置值的四种形态:

===========================  ==================================================
值                           含义
===========================  ==================================================
``""``                       未配置 —— 用 ``DEFAULT_PRESET_ID`` 的内置立绘
``"preset:<id>"``            指定 ``resources/pet/`` 里的某个内置立绘
``"vector"``                 老的自绘矢量小飞宠(``PetSprite.qml`` 内置形体)
``"D:\\pics\\pet.png"``      用户自备图片的绝对路径(原行为,保持兼容)
===========================  ==================================================

立绘清单来自 ``resources/pet/presets.json``;缺这个文件时退化为扫描目录里的
``*.png``,id 取文件名,保证手工放图也能用。

带姿势帧的预设(如 ``navigator``)额外提供 ``frames``:姿势角色 → 文件路径,
角色名与 ``qml/pet/PetSprite.qml`` 的状态机一致(``idle`` / ``blink`` / ``wave`` /
``cheer`` / ``sleepy`` / ``alert``)。清单里不写 ``frames`` 也能用 —— 约定
``resources/pet/<id>/<角色名>.png`` 自动发现;缺某个角色时桌宠退回 ``idle``。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re

LOGGER = logging.getLogger(__name__)

PET_IMAGE_VECTOR = "vector"
PRESET_PREFIX = "preset:"
DEFAULT_PRESET_ID = "navigator"
PRESET_SUBDIR = "pet"
PRESET_MANIFEST = "presets.json"

# 令牌里的 id 只允许安全字符,防止 "preset:../../windows/x" 这类路径穿越。
_PRESET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
# 姿势角色名:小写字母 + 下划线,够覆盖 idle/blink/wave/cheer/sleepy/alert。
FRAME_ROLES = ("idle", "blink", "wave", "cheer", "sleepy", "alert")
_FRAME_ROLE_PATTERN = re.compile(r"^[a-z_]{1,24}$")


@dataclass(frozen=True)
class PetPreset:
    """一个内置立绘选项。

    ``frames`` 是「姿势角色 → 绝对路径」,角色名与 ``PetSprite.qml`` 的状态机对应
    (idle / blink / wave / cheer / sleepy / alert);只有 ``idle`` 或干脆没有 frames
    的预设就是静态立绘,桌宠照常工作。
    """

    id: str
    label: str
    path: str
    exists: bool
    frames: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.frames is None:
            # frozen dataclass 不能直接赋值,绕一下,保持构造调用点简洁。
            object.__setattr__(self, "frames", {})

    @property
    def token(self) -> str:
        return PRESET_PREFIX + self.id

    def to_map(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "token": self.token,
            "path": self.path,
            "exists": self.exists,
            "frames": dict(self.frames),
        }


def pet_image_kind(token: str) -> str:
    """返回 default / vector / preset / custom,供界面判断当前选中的是哪一类。"""
    text = (token or "").strip()
    if not text:
        return "default"
    if text.lower() == PET_IMAGE_VECTOR:
        return "vector"
    if text.startswith(PRESET_PREFIX):
        return "preset"
    return "custom"


def preset_id_of(token: str) -> str:
    """从 ``preset:<id>`` 取出 id;非法返回空串。"""
    text = (token or "").strip()
    if not text.startswith(PRESET_PREFIX):
        return ""
    candidate = text[len(PRESET_PREFIX):].strip()
    return candidate if _PRESET_ID_PATTERN.match(candidate) else ""


def preset_dir_of(resources_dir: str) -> str:
    return os.path.join(resources_dir, PRESET_SUBDIR)


def list_pet_presets(resources_dir: str) -> list[PetPreset]:
    """列出可用的内置立绘(清单缺失时退化为扫描目录)。"""
    directory = preset_dir_of(resources_dir)
    _, entries = _read_manifest(resources_dir)
    if not entries:
        try:
            names = sorted(
                name for name in os.listdir(directory)
                if name.lower().endswith(".png")
            )
        except OSError:
            names = []
        entries = [(os.path.splitext(name)[0], os.path.splitext(name)[0], name, {})
                   for name in names]
    presets = []
    for pid, label, filename, rel_frames in entries:
        path = _native(directory, filename)
        frames = {}
        for role, relative in rel_frames.items():
            candidate = _native(directory, relative)
            if _FRAME_ROLE_PATTERN.match(role) and os.path.isfile(candidate):
                frames[role] = candidate
        if not frames:
            # 清单没写 frames 也能动:约定 <立绘名>/ 目录里的 *.png,文件名即角色名。
            frames = _discover_frames(directory, pid)
        if "idle" not in frames and os.path.isfile(path):
            frames["idle"] = path
        presets.append(PetPreset(id=pid, label=label, path=path,
                                 exists=os.path.isfile(path), frames=frames))
    return presets


def _discover_frames(directory: str, preset_id: str) -> dict[str, str]:
    """按约定发现 ``<立绘目录>/<id>/<role>.png`` 形式的姿势帧。"""
    folder = os.path.join(directory, preset_id)
    if not os.path.isdir(folder):
        return {}
    frames: dict[str, str] = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return {}
    for name in names:
        if not name.lower().endswith(".png"):
            continue
        role = os.path.splitext(name)[0].lower()
        if _FRAME_ROLE_PATTERN.match(role):
            frames[role] = os.path.join(folder, name)
    return frames


def _safe_relative(value: object) -> str:
    """把清单里的相对路径收敛成安全子路径;不合法返回空串。

    不能简单取 basename —— 立绘与姿势帧按约定放在 ``<id>/`` 子目录里。这里只允许
    目录内的相对 .png 路径,拒绝绝对路径、盘符与任何 ``..`` 段,防止清单写到立绘
    目录之外。
    """
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or ":" in text:
        return ""
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return ""
    if not parts[-1].lower().endswith(".png"):
        return ""
    return "/".join(parts)


def _native(directory: str, relative: str) -> str:
    """清单里的相对路径统一用 /,落到本机时再拼成本地分隔符。"""
    return os.path.join(directory, *relative.split("/"))


def _read_manifest(resources_dir: str) -> tuple[str, list[tuple[str, str, str, dict]]]:
    """读 presets.json,返回 (默认 id, [(id, label, 文件名, {角色: 相对路径})])。"""
    manifest = os.path.join(preset_dir_of(resources_dir), PRESET_MANIFEST)
    default_id = ""
    entries: list[tuple[str, str, str, dict]] = []
    if not os.path.isfile(manifest):
        return default_id, entries
    try:
        with open(manifest, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        LOGGER.warning("桌宠立绘清单读取失败,改为扫描目录: %s", exc)
        return default_id, entries
    if not isinstance(payload, dict):
        LOGGER.warning("桌宠立绘清单根节点不是对象,已忽略")
        return default_id, entries
    raw_default = str(payload.get("default", "")).strip()
    if _PRESET_ID_PATTERN.match(raw_default):
        default_id = raw_default
    for item in payload.get("presets", []):
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id", "")).strip()
        if not _PRESET_ID_PATTERN.match(pid):
            continue
        raw_frames = item.get("frames")
        frames: dict[str, str] = {}
        if isinstance(raw_frames, dict):
            for role, relative in raw_frames.items():
                role_text = str(role).strip().lower()
                safe = _safe_relative(relative)
                if _FRAME_ROLE_PATTERN.match(role_text) and safe:
                    frames[role_text] = safe
        safe_file = _safe_relative(item.get("file")) or f"{pid}.png"
        entries.append((pid, str(item.get("label") or pid), safe_file, frames))
    return default_id, entries


def default_preset_token(resources_dir: str) -> str:
    """清单里 default 指向的立绘令牌(清单缺失时退回 ``DEFAULT_PRESET_ID``)。"""
    default_id, _ = _read_manifest(resources_dir)
    return PRESET_PREFIX + (default_id or DEFAULT_PRESET_ID)


def resolve_pet_image(token: str, resources_dir: str) -> str:
    """把配置值翻译成 ``PetSprite.imagePath`` 能直接用的绝对路径。

    返回空串表示"用自绘矢量形体"。内置立绘文件缺失时同样退回矢量,
    不会出现桌宠隐身。
    """
    kind = pet_image_kind(token)
    if kind == "vector":
        return ""
    if kind == "custom":
        return (token or "").strip()
    default_id, _ = _read_manifest(resources_dir)
    wanted = (default_id or DEFAULT_PRESET_ID) if kind == "default" else preset_id_of(token)
    if not wanted:
        return ""
    for preset in list_pet_presets(resources_dir):
        if preset.id.lower() == wanted.lower():
            return preset.path if preset.exists else ""
    return ""


def resolve_pet_frames(token: str, resources_dir: str) -> dict[str, str]:
    """当前令牌所指预设的姿势帧表(角色 → 绝对路径)。

    自绘形体与用户自备图片没有姿势帧,返回空表,界面据此退回单图模式。
    """
    kind = pet_image_kind(token)
    if kind in ("vector", "custom"):
        return {}
    default_id, _ = _read_manifest(resources_dir)
    wanted = (default_id or DEFAULT_PRESET_ID) if kind == "default" else preset_id_of(token)
    if not wanted:
        return {}
    for preset in list_pet_presets(resources_dir):
        if preset.id.lower() == wanted.lower():
            return dict(preset.frames)
    return {}
