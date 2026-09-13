# coding: utf-8
"""系统托盘图标：主窗口收进托盘后还能叫回来，并提供一个明确的「退出程序」入口。

这里刻意**不**改变关闭语义：点窗口 X 由 ``qml/dialogs/CloseChoiceDialog.qml``
问一句「退出程序 / 最小化到托盘 / 取消」（见 ``qml/main.qml``），托盘只负责
被叫回来时给两个出口，绝不静默把程序收进托盘。

退出动作用信号发出去（``quitRequested``），由入口把它接到
``QCoreApplication.quit()``：这样托盘、QML 对话框、桌宠菜单三条退出路径
在 Python 侧只有一个落点，测试也能直接连信号断言，不必真去跑事件循环。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon
from prismqml import SystemTrayIcon

LOGGER = logging.getLogger(__name__)

SHOW_ACTION = "trayShowMainWindow"
QUIT_ACTION = "trayQuit"

# 托盘图标被左键/双击激活时叫回主窗口。prismqml 的 SystemTrayIcon.activated 发的是
# Qt 枚举的 int 值(见其 _on_activated)，所以这里按 Qt 的枚举比对，不去依赖
# prismqml 内部模块路径（顶层的 ActivationReason 在 0.4.2 里其实导不出来）。
_CLICK_REASONS = frozenset({
    int(QSystemTrayIcon.ActivationReason.Trigger.value),
    int(QSystemTrayIcon.ActivationReason.DoubleClick.value),
})


class AppTrayController(QObject):
    """托盘图标 + 两个菜单动作。左键/双击叫回主窗口，右键出菜单。"""

    quitRequested = Signal()

    def __init__(self, tray: SystemTrayIcon, window: QObject, parent: QObject = None):
        super().__init__(parent or window)
        self._tray = tray
        self._window = window
        tray.addAction("显示主界面", actionId=SHOW_ACTION,
                       triggered=self.showMainWindow)
        tray.addSeparator()
        tray.addAction("退出程序", actionId=QUIT_ACTION, triggered=self.requestQuit)
        tray.activated.connect(self._on_activated)
        tray.show()

    # ------------------------------------------------------------------ 动作

    def showMainWindow(self) -> None:  # noqa: N802 - 与 Qt 命名保持一致
        """从托盘叫回主窗口:显示 + 抬到最前 + 抢焦点。"""
        window = self._window
        if window is None:
            return
        window.show()
        if hasattr(window, "raise_"):
            window.raise_()
        if hasattr(window, "requestActivate"):
            window.requestActivate()

    def requestQuit(self) -> None:  # noqa: N802 - 与 Qt 命名保持一致
        self.quitRequested.emit()

    # ------------------------------------------------------------------ 自检

    @property
    def action_texts(self) -> List[str]:
        """菜单项文案(不含分隔线),供测试与自检核对。"""
        return [
            action["text"]
            for action in self._tray.actions()
            if not action.get("separator")
        ]

    # ------------------------------------------------------------------ 内部

    def _on_activated(self, reason: int) -> None:
        # 左键/双击叫回窗口;右键由 SystemTrayIcon 自己弹菜单,这里不重复处理。
        if int(reason) in _CLICK_REASONS:
            self.showMainWindow()


def install_app_tray(window: Optional[QObject], icon_path: str,
                     tool_tip: str) -> Optional[AppTrayController]:
    """创建托盘图标;系统不支持托盘或主窗口缺失时返回 None,不影响程序启动。"""
    if window is None:
        LOGGER.warning("主窗口尚未创建,跳过托盘图标")
        return None
    if not SystemTrayIcon.isSystemTrayAvailable():
        LOGGER.info("当前系统没有可用的通知区域,跳过托盘图标")
        return None
    tray = SystemTrayIcon(icon=icon_path, parent=window, toolTip=tool_tip,
                          menuOnLeftClick=False)
    return AppTrayController(tray, window)
