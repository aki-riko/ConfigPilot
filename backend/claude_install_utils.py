# coding: utf-8
"""Claude 安装下载共用的无状态辅助函数。"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
from urllib.parse import urlparse

from backend.claude_install_sources import InstallSpec


LOGGER = logging.getLogger(__name__)


def remove_download_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return
    except OSError:
        LOGGER.warning("清理 Claude 下载目录失败: %s", path, exc_info=True)


def format_bytes(value: int) -> str:
    amount = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{int(value)} B"


def validate_response_url(url: str, spec: InstallSpec) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in spec.allowed_hosts:
        raise RuntimeError(f"下载被重定向到未授权地址: {hostname or url}")


def content_length(headers, maximum: int) -> int:
    raw = headers.get("Content-Length", "")
    if not raw:
        return 0
    try:
        length = int(raw)
    except ValueError as exc:
        raise RuntimeError("服务器返回了无效的文件大小") from exc
    if length <= 0 or length > maximum:
        raise RuntimeError("服务器返回的文件大小超出安全限制")
    return length


def request(spec: InstallSpec, url: str, accept: str):
    from urllib import request as urllib_request

    headers = {"User-Agent": spec.user_agent, "Accept": accept}
    return urllib_request.Request(url, headers=headers)
