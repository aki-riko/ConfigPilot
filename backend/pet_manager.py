# coding: utf-8
"""桌宠开关与窗口生命周期管理。

主界面设置页的开关、桌宠右键菜单的「设置…」都经过这里:
- 开关只控制 auto_show 配置与悬浮窗显隐,窗口对象按需创建并复用;
- 设置窗口同样懒创建,通过 openSettingsRequested 信号让 QML 自己弹出;
- 用户从菜单「退出桌宠」关闭窗口时,同步把开关置为关闭并落盘。
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from backend.newapi_pet import NewApiPet


LOGGER = logging.getLogger(__name__)


class PetManager(QObject):
    """暴露给 QML 的桌宠开关(PetManager 上下文属性)。"""

    enabledChanged = Signal()
    hasKeyChanged = Signal()
    openSettingsRequested = Signal()

    def __init__(
        self,
        controller: NewApiPet,
        window_factory: Callable[[], Optional[QObject]],
        settings_factory: Callable[[], Optional[QObject]],
        standalone: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._window_factory = window_factory
        self._settings_factory = settings_factory
        self._standalone = standalone
        self._window: Optional[QObject] = None
        self._settings_window: Optional[QObject] = None
        # 独立入口没有主窗口,启动即显示;集成模式由 auto_show 决定。
        self._enabled = standalone or controller.config.auto_show
        controller.configSaved.connect(self._on_controller_config_saved)
        controller.statusChanged.connect(self._refresh_has_key)

    # ------------------------------------------------------------------ 属性

    @Property(bool, notify=enabledChanged)
    def petEnabled(self) -> bool:
        return self._enabled

    @Property(bool, notify=hasKeyChanged)
    def petHasApiKey(self) -> bool:
        # 复用 Codex/Claude 时也算"已配置":以解析出的凭证为准。
        return bool(self._controller.sourceReady)

    # ------------------------------------------------------------------ 槽

    @Slot(bool)
    def setEnabled(self, enabled: bool) -> None:
        """主界面开关:持久化 auto_show 并显示/隐藏悬浮窗。"""
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self.enabledChanged.emit()
        self._controller.setAutoShow(enabled)
        if enabled:
            self._show_window()
        else:
            self._hide_window()

    @Slot()
    def openSettings(self) -> None:
        """打开(或唤起)桌宠设置窗口。"""
        if self._settings_window is None:
            self._settings_window = self._settings_factory()
            if self._settings_window is None:
                LOGGER.warning("桌宠设置窗口创建失败")
                return
        self.openSettingsRequested.emit()

    @Slot()
    def petWindowClosed(self) -> None:
        """QML 侧关闭悬浮窗(右键菜单「退出桌宠」)时同步开关状态。"""
        if self._standalone:
            return
        if self._enabled:
            self._enabled = False
            self.enabledChanged.emit()
            self._controller.setAutoShow(False)

    # ------------------------------------------------------------------ 内部

    def show_at_startup(self) -> None:
        """应用启动完成后调用:开关为开时显示桌宠。"""
        if self._enabled:
            self._show_window()

    def _show_window(self) -> None:
        if self._window is None:
            self._window = self._window_factory()
            if self._window is None:
                LOGGER.warning("桌宠悬浮窗创建失败")
                return
        self._window.setVisible(True)
        self._controller.refresh()

    def _hide_window(self) -> None:
        if self._window is not None:
            self._window.setVisible(False)

    def _on_controller_config_saved(self) -> None:
        self._refresh_has_key()
        # 保存设置后若开关为开,确保桌宠可见(例如首次配置 Key)。
        if self._enabled:
            self._show_window()

    def _refresh_has_key(self) -> None:
        self.hasKeyChanged.emit()
