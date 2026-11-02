# coding: utf-8
"""Authenticode 代码签名（本地手动发版用）。

证书：Certum Code Signing（云端 HSM，SimplySign Desktop）
主体：CN=福州市晋安区棱镜映界软件工作室（个体工商户），有效期至 2027-10-20

为什么只能在本地手动签：
    Certum 官方不支持 CI 管线签名；且登录需要手机 TOTP 动态码，2 小时后会话
    自动失效。把 TOTP seed 放进 CI secret 等于把签名权交给任何能读 secret 的人。

职责：
    1. 定位 signtool.exe（Windows SDK）
    2. 对白名单里的自有可执行文件逐个签名（SHA256 + RFC3161 时间戳）
    3. 每个文件签完立刻 signtool verify /pa 校验，任一失败即 fail-closed

使用：
    .venv\\Scripts\\python.exe scripts\\sign_authenticode.py build\\main.dist\\ConfigPilot.exe
    .venv\\Scripts\\python.exe scripts\\sign_authenticode.py installer\\ConfigPilot_Setup_1.0.35.exe
    .venv\\Scripts\\python.exe scripts\\sign_authenticode.py --verify <文件...>
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 证书指纹是公开信息，不是凭据：signtool /sha1 靠它从证书库挑证书，
# 拿不到私钥。私钥始终在 Certum 云端 HSM，从不落盘。
DEFAULT_THUMBPRINT = "C1D40B747ADF62325B6ED70434E4AC8CF8BD60EC"
# Certum 提供的免费 RFC3161 时间戳。不要用 public-qlts.certum.pl（付费合格时间戳）。
DEFAULT_TIMESTAMP_URL = "http://time.certum.pl"


class SigningError(RuntimeError):
    """签名或校验失败（fail-closed）。"""


def _expand(value: str) -> str:
    """展开 ${VAR} / %VAR% 与 ~。

    os.path.expandvars 对不存在的变量会原样返回，这里主动检测残留占位符并
    报错，避免把字面量当真实值传给 signtool。
    """
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    if "${" in expanded or re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", expanded):
        raise SigningError(
            f"配置值未能展开（环境变量未设置）: {value!r} -> {expanded!r}"
        )
    return expanded


def find_signtool(explicit: str | None = None) -> Path:
    """定位 signtool.exe：优先显式路径，其次 Windows Kits 下版本号最高的 x64。"""
    if explicit:
        candidate = Path(_expand(explicit))
        if candidate.is_file():
            return candidate
        raise SigningError(f"指定的 signtool 不存在: {candidate}")

    roots = [
        Path(os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)")
        / "Windows Kits" / "10" / "bin",
        Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
        / "Windows Kits" / "10" / "bin",
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            candidates.extend(root.glob("*/x64/signtool.exe"))
    if not candidates:
        raise SigningError(
            "未找到 signtool.exe：请安装 Windows SDK，或用 --signtool 指定完整路径"
        )

    def _version_key(path: Path) -> tuple:
        # <bin>/<10.0.x.y>/x64/signtool.exe
        parts = path.parent.parent.name.split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return (0,)

    candidates.sort(key=_version_key, reverse=True)
    return candidates[0]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def sign_file(
    signtool: Path, target: Path, thumbprint: str, timestamp_url: str
) -> None:
    """对单个文件执行 Authenticode 签名（SHA256 + RFC3161 时间戳）。"""
    cmd = [
        str(signtool),
        "sign",
        "/sha1", thumbprint,
        "/fd", "SHA256",
        "/tr", timestamp_url,
        "/td", "SHA256",
        "/v",
        str(target),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise SigningError(
            f"签名失败 (exit={result.returncode}): {target}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n"
            "常见原因：SimplySign Desktop 未登录 / 会话超过 2 小时 / 证书指纹不匹配 / "
            "时间戳服务器不可达。重新登录 SimplySign 后重试即可。"
        )


def verify_file(signtool: Path, target: Path) -> None:
    """校验已签文件；签名无效、时间戳缺失或吊销检查失败都视为失败。

    不能只信 `signtool verify` 的退出码：某些情况下它会对「没有任何签名」的
    文件也返回成功。这里额外用 Get-AuthenticodeSignature 复核 Status 与
    时间戳证书，两者都必须有效，否则视为未签名。
    """
    cmd = [str(signtool), "verify", "/pa", "/v", str(target)]
    result = _run(cmd)
    if result.returncode != 0:
        raise SigningError(
            f"签名校验失败 (exit={result.returncode}): {target}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    status, has_timestamp = _read_signature_state(target)
    if status != "Valid":
        raise SigningError(
            f"签名状态不是 Valid（实际 {status}）: {target}\n"
            "该文件可能根本没有签名，或证书链/吊销检查失败。"
        )
    if not has_timestamp:
        raise SigningError(
            f"签名缺少时间戳: {target}\n"
            "没有 RFC3161 时间戳的签名在证书过期后会失效，不能发布。"
        )


def _read_signature_state(target: Path) -> tuple[str, bool]:
    """返回 (Status, 是否有时间戳证书)。

    只输出两个由换行分隔的简单值，不在 PowerShell 里做字符串拼接——
    拼接写法在部分代码页下会被解析器判为语法错误。
    """
    escaped = str(target).replace("'", "''")
    script = (
        f"$s = Get-AuthenticodeSignature '{escaped}'; "
        "$s.Status.ToString(); "
        "if ($null -eq $s.TimeStamperCertificate) { 'False' } else { 'True' }"
    )
    result = _run(["powershell", "-NoProfile", "-Command", script])
    if result.returncode != 0:
        raise SigningError(
            f"读取签名状态失败: {target}\n{result.stdout}\n{result.stderr}"
        )
    lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
    status = lines[0] if lines else ""
    has_timestamp = len(lines) > 1 and lines[1] == "True"
    return status, has_timestamp


def describe_signature(target: Path) -> str:
    """返回可读的签名摘要，用于发版记录与人工核对。

    每项单独输出一行，不在 PowerShell 内拼接字符串（见 _read_signature_state）。
    """
    escaped = str(target).replace("'", "''")
    script = (
        f"$s = Get-AuthenticodeSignature '{escaped}'; "
        "'Status: ' + $s.Status.ToString(); "
        "$s.SignerCertificate.Subject; "
        "$s.TimeStamperCertificate.Subject"
    )
    result = _run(["powershell", "-NoProfile", "-Command", script])
    return result.stdout.strip() if result.returncode == 0 else "(读取签名信息失败)"


def sign_targets(
    targets: list[Path],
    *,
    thumbprint: str = DEFAULT_THUMBPRINT,
    timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    signtool_path: str | None = None,
) -> None:
    """对给定文件逐个签名并立即校验。任一失败即抛错，不做降级。"""
    if not targets:
        raise SigningError("没有指定待签文件")

    signtool = find_signtool(signtool_path)
    print(f"[sign] signtool : {signtool}")
    print(f"[sign] 证书指纹 : {thumbprint}")
    print(f"[sign] 时间戳   : {timestamp_url}")

    for target in targets:
        if not target.is_file():
            raise SigningError(f"待签文件不存在: {target}")
        print(f"\n[sign] 签名 {target.name} ({target.stat().st_size:,} 字节)")
        sign_file(signtool, target, thumbprint, timestamp_url)
        verify_file(signtool, target)
        print(f"[sign] ✅ {target.name} 已签名并通过校验")

    print(f"\n[sign] 完成：{len(targets)} 个文件")


def verify_targets(
    targets: list[Path], *, signtool_path: str | None = None
) -> None:
    """只校验、不签名。用于核对既有产物，避免重复消耗签名额度。"""
    if not targets:
        raise SigningError("没有指定待校验文件")
    signtool = find_signtool(signtool_path)
    for target in targets:
        if not target.is_file():
            raise SigningError(f"待校验文件不存在: {target}")
        verify_file(signtool, target)
        print(f"[sign] ✅ {target.name} 签名有效")
        print(describe_signature(target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ConfigPilot Authenticode 签名（本地手动发版）"
    )
    parser.add_argument("files", nargs="+", help="待签/待校验的文件路径")
    parser.add_argument(
        "--verify", action="store_true", help="只校验，不签名"
    )
    parser.add_argument(
        "--thumbprint", default=DEFAULT_THUMBPRINT, help="证书指纹"
    )
    parser.add_argument(
        "--timestamp-url", default=DEFAULT_TIMESTAMP_URL, help="RFC3161 时间戳地址"
    )
    parser.add_argument("--signtool", default=None, help="signtool.exe 完整路径")
    args = parser.parse_args(argv)

    targets = [Path(p).resolve() for p in args.files]
    try:
        if args.verify:
            verify_targets(targets, signtool_path=args.signtool)
        else:
            sign_targets(
                targets,
                thumbprint=args.thumbprint.replace(" ", ""),
                timestamp_url=args.timestamp_url,
                signtool_path=args.signtool,
            )
    except SigningError as exc:
        print(f"[sign] ❌ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
