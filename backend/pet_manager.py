# coding: utf-8
"""桌宠开关与窗口生命周期管理。

主界面设置页的开关、桌宠右键菜单的「设置…」都经过这里:
- 开关只控制 auto_show 配置与悬浮窗显隐,窗口对象按需创建并复用;
- 设置窗口同样懒创建,通过 openSettingsRequested 信号让 QML 自己弹出;
- 用户从菜单「退出程序」离开时走 Qt.quit()，不经过这里：退出意图不该顺手改掉开关。
  只有窗口被单独关闭（例如设置页把桌宠关掉）才同步把开关置为关闭并落盘。
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
    visibleChanged = Signal()
    openSettingsRequested = Signal()

    def __init__(
        self,
        controller: NewApiPet,
        window_factory: Callable[[], Optional[QObject]],
        settings_factory: Callable[[], Optional[QObject]],
        standalone: bool = False,
        parent: QObject | None = None,
        main_window: QObject | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._window_factory = window_factory
        self._settings_factory = settings_factory
        self._standalone = standalone
        self._window: Optional[QObject] = None
        self._settings_window: Optional[QObject] = None
        # 桌宠寿命跟随主窗口:主窗口隐藏(关闭到托盘)时桌宠一并隐藏,
        # 主窗口重新出现时再按开关恢复。独立入口没有主窗口,不受此约束。
        self._main_window = main_window
        # 主窗口尚未显示时创建的桌宠窗口先保持隐藏,由主窗口可见后统一显示。
        # 构造时主窗口已经可见(启动时挂载)则直接进入就绪状态。
        self._lifecycle_ready = main_window is None or bool(main_window.isVisible())
        # 独立入口没有主窗口,启动即显示;集成模式由 auto_show 决定。
        self._enabled = standalone or controller.config.auto_show
        controller.configSaved.connect(self._on_controller_config_saved)
        controller.statusChanged.connect(self._refresh_has_key)
        if main_window is not None:
            signal = getattr(main_window, "visibilityChanged", None)
            if signal is not None:
                signal.connect(self._on_main_window_visibility_changed)

    # ------------------------------------------------------------------ 属性

    @Property(bool, notify=enabledChanged)
    def petEnabled(self) -> bool:
        return self._enabled

    @Property(bool, notify=hasKeyChanged)
    def petHasApiKey(self) -> bool:
        # 复用 Codex/Claude 时也算"已配置":以解析出的凭证为准。
        return bool(self._controller.sourceReady)

    @Property(bool, notify=visibleChanged)
    def petVisible(self) -> bool:
        """桌宠悬浮窗当前是否真的显示着(受开关与主窗口可见性共同约束)。"""
        if self._window is None:
            return False
        query = getattr(self._window, "isVisible", None)
        if query is None:
            return False
        return bool(query())

    # ------------------------------------------------------------------ 槽

    @Slot(float, float, result=float)
    def clampTipCenterX(self, desired_window_x: float, tip_width: float) -> float:
        """把气泡弹层的水平中心夹进屏幕可用区,返回窗口坐标下的中心 x。

        框架的 TipPopup 只按 target 中心摆放、且不做屏幕避让(见 prismqml 的
        TipPositionHelper::calculatePosition),所以"箭头对准桌宠脑袋"和"弹层不出屏"
        只能由调用方一起满足。窗口与屏幕几何都在 Qt 侧取,单位一致(设备无关像素)。
        """
        window = self._window
        if window is None or tip_width <= 0:
            return desired_window_x
        screen = window.screen()
        if screen is None:
            return desired_window_x
        area = screen.availableGeometry()
        margin = 4.0
        half = tip_width / 2.0
        # 换算到窗口坐标:窗口左上角在屏幕坐标 window.x()/window.y()
        low = area.left() + margin + half - window.x()
        high = area.left() + area.width() - margin - half - window.x()
        if low > high:
            return desired_window_x
        return max(low, min(high, desired_window_x))

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
        """QML 侧单独关闭悬浮窗时同步开关状态（右键「退出程序」不走这里）。"""
        if self._standalone:
            return
        if self._enabled:
            self._enabled = False
            self.enabledChanged.emit()
            self._controller.setAutoShow(False)

    # ------------------------------------------------------------------ 内部

    def show_at_startup(self) -> None:
        """应用启动完成后调用:开关为开且主窗口可见时显示桌宠。"""
        if self._main_window is not None and not bool(self._main_window.isVisible()):
            return
        self._lifecycle_ready = True
        if self._enabled:
            self._show_window()

    def _show_window(self) -> None:
        if self._window is None:
            self._window = self._window_factory()
            if self._window is None:
                LOGGER.warning("桌宠悬浮窗创建失败")
                return
        # 主窗口未显示时先不露出桌宠,等主窗口出现再跟着出现。
        if self._lifecycle_ready and not self._main_window_hidden():
            self._window.setVisible(True)
        self.visibleChanged.emit()
        # 不在此处强制刷新:控制器自带轮询计时器,数据本就保持新鲜;
        # 每次显示都打一发会白白消耗 new-api 的限流配额。

    def _hide_window(self) -> None:
        if self._window is not None:
            self._window.setVisible(False)
            self.visibleChanged.emit()

    def _main_window_hidden(self) -> bool:
        if self._main_window is None:
            return False
        return not bool(self._main_window.isVisible())

    def _on_main_window_visibility_changed(self) -> None:
        """主窗口显隐变化:桌宠跟随隐藏/恢复(开关关闭时不复活)。"""
        if self._main_window_hidden():
            self._hide_window()
            return
        # 首次可见即视为生命周期就绪,此后开关是唯一的显示条件。
        self._lifecycle_ready = True
        if self._enabled:
            self._show_window()

    def _on_controller_config_saved(self) -> None:
        self._refresh_has_key()
        # 保存设置后若开关为开,确保桌宠可见(例如首次配置 Key)。
        if self._enabled:
            self._show_window()

    def _refresh_has_key(self) -> None:
        self.hasKeyChanged.emit()
