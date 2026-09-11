# coding: utf-8
"""配置目录自愈工具。

背景：部分第三方"一键配置脚本"会把 ~/.codex 误创建为普通文件（如 PowerShell
New-Item 漏写 -ItemType Directory、echo xxx > .codex 等），或留下指向不存在
目标的符号链接/junction。此时 os.makedirs(..., exist_ok=True) 仍会抛出
[WinError 183] 当文件已存在时，无法创建该文件。

ensure_directory() 在写入前统一处理该情形：把占用者改名备份（绝不删除，内容
可恢复），重建真正的目录后继续写入，对用户静默无感。
"""

from __future__ import annotations

import logging
import os
import time

LOGGER = logging.getLogger(__name__)


def _reserve_backup_path(path: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = f"{path}.file-{stamp}"
    index = 1
    while os.path.lexists(candidate):
        candidate = f"{path}.file-{stamp}-{index}"
        index += 1
    return candidate


def ensure_directory(path: str) -> str | None:
    """确保 path 是可用的目录。

    若 path 被同名文件/坏链接占用，则将其改名为 "<path>.file-<时间戳>" 备份
    并重建目录，返回备份路径；无需修复时返回 None。权限不足等硬错误照常抛出，
    由上层按"写入失败"提示用户。
    """
    if os.path.isdir(path):
        return None
    try:
        os.makedirs(path, exist_ok=True)
        return None
    except FileExistsError:
        pass
    # path 存在但不是目录（普通文件 / 指向不存在目标的符号链接或 junction）。
    backup = _reserve_backup_path(path)
    try:
        os.rename(path, backup)
    except FileNotFoundError:
        # 并发下占用者已被其它进程移走，直接重试建目录即可。
        os.makedirs(path, exist_ok=True)
        return None
    LOGGER.warning("检测到 %s 不是目录，已备份为 %s 并重建目录", path, backup)
    os.makedirs(path, exist_ok=True)
    return backup
