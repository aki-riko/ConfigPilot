# coding: utf-8
"""ConfigPilot 本地一键发版（含 Authenticode 签名）。

为什么是本地脚本而不是 CI：
    证书私钥在 Certum 云端 HSM，登录需要手机 TOTP 动态码且 2 小时会话失效；
    Certum 官方也不支持在 CI 管线里签名。把 TOTP seed 放进 CI secret 等于把
    签名权交给任何能读 secret 的人。

流程（顺序不可调换）：
    1. 前置检查：分支/工作区干净/版本号/签名环境（signtool + SimplySign + 证书）
    2. Nuitka 打包 → build\\main.dist\\ConfigPilot.exe
    3. 【签名主程序】——必须在打安装包之前，签名会改变文件字节
    4. ISCC 生成 Setup.exe
    5. 【签名安装包】——签在发布之前
    6. 校验产物签名 + 打印摘要

使用：
    .venv\\Scripts\\python.exe scripts\\release_windows.py            # 完整发版
    .venv\\Scripts\\python.exe scripts\\release_windows.py --skip-build   # 跳过 Nuitka
    .venv\\Scripts\\python.exe scripts\\release_windows.py --dry-run      # 只做检查
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import sign_authenticode as signing  # noqa: E402

APP_CONFIG = PROJECT_ROOT / "app_config.json"
EXPECTED_APP_NAME = "ConfigPilot.exe"
MAIN_DIST = PROJECT_ROOT / "build" / "main.dist"
INSTALLER_DIR = PROJECT_ROOT / "installer"
ISS_FILE = PROJECT_ROOT / "ConfigPilot.iss"


class ReleaseError(RuntimeError):
    """发版前置条件或产物检查失败。"""


def _run(cmd: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise ReleaseError(f"命令失败 (exit={result.returncode}): {' '.join(cmd)}")


def read_version() -> str:
    data = json.loads(APP_CONFIG.read_text(encoding="utf-8"))
    version = str(data.get("version") or "").strip()
    if not version:
        raise ReleaseError(f"{APP_CONFIG} 缺少 version")
    return version


def find_iscc() -> Path:
    """定位 ISCC.exe：先认程序目录，再认 PATH。"""
    candidates = [
        Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    which = shutil.which("ISCC")
    if which:
        return Path(which)
    raise ReleaseError(
        "未找到 ISCC.exe：请安装 Inno Setup 6/7，或把它加入 PATH"
    )


def check_signing_ready() -> Path:
    """确认签名三要素就绪：signtool / SimplySign 进程 / 证书。"""
    signtool = signing.find_signtool()
    print(f"[check] signtool  : {signtool}")

    process = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process -Name '*SimplySign*' -ErrorAction SilentlyContinue | "
         "Measure-Object).Count"],
        capture_output=True, text=True,
    )
    running = (process.stdout or "").strip()
    if running in ("", "0"):
        raise ReleaseError(
            "SimplySign Desktop 未运行。请先启动并完成 TOTP 登录再发版。"
        )
    print(f"[check] SimplySign: 运行中（{running} 个进程）")

    thumbprint = signing.DEFAULT_THUMBPRINT
    cert_script = (
        f"$c = Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert | "
        f"Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}; "
        "if ($c) { 'Found=' + $c.NotAfter.ToString('yyyy-MM-dd') } else { 'Found=' }"
    )
    cert = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cert_script],
        capture_output=True, text=True,
    )
    found = ""
    for line in (cert.stdout or "").splitlines():
        if line.strip().startswith("Found="):
            found = line.split("=", 1)[1].strip()
    if not found:
        raise ReleaseError(
            f"证书库里找不到指纹为 {thumbprint} 的代码签名证书。"
            "请确认 SimplySign 已挂载证书。"
        )
    print(f"[check] 证书有效期至: {found}")
    return signtool


def build_standalone(version: str) -> Path:
    """用 Nuitka 打包成 standalone 目录。"""
    python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        raise ReleaseError(f"未找到虚拟环境解释器: {python}")

    import prismqml  # noqa: PLC0415

    fq = Path(prismqml.__file__).parent
    if MAIN_DIST.exists():
        shutil.rmtree(MAIN_DIST.parent, ignore_errors=True)

    _run([
        str(python), "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=qml",
        "--include-data-dir=qml=qml",
        "--include-data-dir=resources=resources",
        f"--include-data-dir={fq}=prismqml",
        "--include-data-files=providers.json=providers.json",
        "--include-data-files=model_profiles.json=model_profiles.json",
        "--include-data-files=app_config.json=app_config.json",
        "--include-package=prismqml",
        "--include-package=backend",
        "--windows-console-mode=disable",
        "--windows-icon-from-ico=resources/app_icon.ico",
        "--output-dir=build",
        f"--output-filename={EXPECTED_APP_NAME}",
        "--company-name=9li",
        "--product-name=ConfigPilot",
        f"--file-version={version}",
        "main.py",
    ])

    exe = MAIN_DIST / EXPECTED_APP_NAME
    if not exe.is_file():
        raise ReleaseError(f"Nuitka 未产出预期文件: {exe}")
    return exe


def build_installer(version: str) -> Path:
    """用 ISCC 生成安装包。"""
    iscc = find_iscc()
    text = ISS_FILE.read_text(encoding="utf-8")
    # 版本号以 app_config.json 为准：直接改写 .iss 的 AppVer 默认值，
    # 避免两处版本脱钩（CI 里用 sed 做同一件事）。
    import re

    updated, count = re.subn(
        r'#define AppVer "[0-9][0-9.]*"',
        f'#define AppVer "{version}"',
        text,
    )
    if count == 0:
        raise ReleaseError("ConfigPilot.iss 里找不到 AppVer 定义")
    if updated != text:
        ISS_FILE.write_text(updated, encoding="utf-8")
        print(f"[build] 已把 .iss 的 AppVer 同步为 {version}")

    _run([str(iscc), str(ISS_FILE)])

    setup = INSTALLER_DIR / f"ConfigPilot_Setup_{version}.exe"
    if not setup.is_file():
        raise ReleaseError(f"ISCC 未产出预期安装包: {setup}")
    return setup


def check_clean_git() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True,
    )
    dirty = (result.stdout or "").strip()
    if dirty:
        raise ReleaseError(
            "工作区不干净，先提交或还原改动再发版:\n" + dirty
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ConfigPilot 本地一键发版")
    parser.add_argument("--skip-build", action="store_true", help="跳过 Nuitka 打包")
    parser.add_argument("--skip-sign", action="store_true", help="跳过签名（仅供调试）")
    parser.add_argument("--dry-run", action="store_true", help="只做前置检查")
    args = parser.parse_args(argv)

    try:
        version = read_version()
        print(f"[release] 版本: {version}")
        check_clean_git()
        print("[release] 工作区干净 ✅")

        if not args.skip_sign:
            check_signing_ready()

        if args.dry_run:
            print("[release] dry-run 完成：前置检查全部通过")
            return 0

        if args.skip_build:
            exe = MAIN_DIST / EXPECTED_APP_NAME
            if not exe.is_file():
                raise ReleaseError(f"--skip-build 但产物不存在: {exe}")
            print(f"[release] 复用既有主程序: {exe}")
        else:
            exe = build_standalone(version)
            print(f"[release] 主程序已生成: {exe}")

        if not args.skip_sign:
            # 必须先签主程序再打安装包：签名改变文件字节。
            signing.sign_targets([exe])
            print("[release] 主程序签名完成 ✅")

        setup = build_installer(version)
        print(f"[release] 安装包已生成: {setup}")

        if not args.skip_sign:
            signing.sign_targets([setup])
            print("[release] 安装包签名完成 ✅")
            print("\n[release] 签名摘要:")
            print(signing.describe_signature(setup))

        print(f"\n[release] 完成。产物: {setup}")
        print("[release] 下一步：上传到 GitHub Release 并打 tag")
        return 0
    except (ReleaseError, signing.SigningError) as exc:
        print(f"\n[release] ❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
