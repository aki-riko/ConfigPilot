# coding: utf-8
"""关闭主窗口的行为偏好：点 ✕ 时问一次，问完可以记住，下次不再弹窗。

三档行为：
- ``ask``    每次点 ✕ 都弹三选一（默认，保持原有行为）；
- ``tray``   直接最小化到托盘，不弹窗；
- ``quit``   直接退出程序，不弹窗。

配置文件和桌宠配置同目录（``ConfigPilot/close_behavior.json``），
读写容错口径也一致：文件缺失/损坏时回落到 ``ask``，绝不让应用起不来。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

_WINDOWS_CONFIG_ROOT_ENVIRONMENT = "LOCALAPPDATA"
_XDG_CONFIG_HOME_ENVIRONMENT = "XDG_CONFIG_HOME"
_APPLICATION_CONFIG_DIR_NAME = "ConfigPilot"
_CLOSE_BEHAVIOR_FILE_NAME = "close_behavior.json"

ASK = "ask"
TRAY = "tray"
QUIT = "quit"
VALID_BEHAVIORS = (ASK, TRAY, QUIT)


def resolve_close_behavior_path(
    platform_name: str | None = None,
    environment: dict[str, str] | None = None,
    home: str | Path | None = None,
) -> Path:
    """返回关闭行为配置文件路径，目录约定与 app_settings / pet_config 一致。"""
    current_platform = platform_name or os.name
    current_environment = environment if environment is not None else os.environ
    if current_platform == "nt":
        config_root = current_environment.get(_WINDOWS_CONFIG_ROOT_ENVIRONMENT)
        if not config_root:
            raise RuntimeError("LOCALAPPDATA 未设置，无法定位 ConfigPilot 配置目录")
        base_path = Path(config_root)
    else:
        xdg_config_home = current_environment.get(_XDG_CONFIG_HOME_ENVIRONMENT)
        base_path = (
            Path(xdg_config_home)
            if xdg_config_home
            else (Path(home) if home is not None else Path.home()) / ".config"
        )
    return base_path / _APPLICATION_CONFIG_DIR_NAME / _CLOSE_BEHAVIOR_FILE_NAME


def normalize_behavior(value: object) -> str:
    """把任意输入收敛成合法档位；不认识的一律回落到 ``ask``。"""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in VALID_BEHAVIORS:
            return normalized
    return ASK


def load_close_behavior(path: str | Path) -> str:
    """读取已记住的关闭行为；文件缺失或损坏时返回 ``ask``，不抛异常。"""
    config_path = Path(path)
    try:
        raw = config_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return ASK
    if not isinstance(data, dict):
        return ASK
    return normalize_behavior(data.get("behavior"))


def save_close_behavior(path: str | Path, behavior: str) -> None:
    """原子写入关闭行为：先写临时文件再替换，避免半截文件。"""
    config_path = Path(path)
    normalized = normalize_behavior(behavior)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_name(config_path.name + ".tmp")
    payload = json.dumps({"behavior": normalized}, ensure_ascii=False, indent=2)
    temporary_path.write_text(payload + "\n", encoding="utf-8")
    os.replace(temporary_path, config_path)


class CloseBehaviorStore(QObject):
    """暴露给 QML 的关闭行为存取器。

    QML 侧读 ``closeBehavior``（"ask"/"tray"/"quit"），写完调 ``setBehavior``。
    每次写入都会发 ``behaviorChanged``，主窗口据此立刻按新档位工作。
    """

    behaviorChanged = Signal()

    def __init__(self, path: str | Path | None = None, parent: QObject = None):
        super().__init__(parent)
        self._path = Path(path) if path is not None else resolve_close_behavior_path()
        self._behavior = load_close_behavior(self._path)

    # ---------------------------------------------------------------- 属性

    def _get_behavior(self) -> str:
        return self._behavior

    closeBehavior = Property(
        str, _get_behavior, notify=behaviorChanged
    )

    # ---------------------------------------------------------------- 方法

    @Slot(str)
    def setBehavior(self, behavior: str) -> None:  # noqa: N802 - QML 可调用
        """记住用户的选择；``ask`` 表示恢复成每次询问。"""
        normalized = normalize_behavior(behavior)
        if normalized == self._behavior:
            return
        self._behavior = normalized
        try:
            save_close_behavior(self._path, normalized)
        except OSError:
            # 落盘失败不能拖垮应用：内存里仍然按新档位工作，
            # 只是下次启动会回到旧值（caller 可见 behaviorChanged 已发出）。
            pass
        self.behaviorChanged.emit()

    @Slot()
    def resetToAsk(self) -> None:  # noqa: N802 - QML 可调用
        """恢复成「每次询问」。"""
        self.setBehavior(ASK)

    def behavior(self) -> str:
        """Python 侧读取当前档位。"""
        return self._behavior
