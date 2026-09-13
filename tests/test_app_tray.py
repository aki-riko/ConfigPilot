# coding: utf-8
"""系统托盘控制器测试。

托盘只在「用户自己选了最小化到托盘」之后提供两个出口：叫回主窗口、退出程序。
这里验证接线正确性，不依赖真实通知区域（offscreen 下
``QSystemTrayIcon.isSystemTrayAvailable()`` 为假，真托盘那组会自动跳过）：

1. 主窗口缺失或系统没有托盘时安静降级（返回 None，不影响启动）；
2. 菜单两项文案/ID 固定，顺序固定，中间有分隔线；
3. 「显示主界面」真的把隐藏的窗口叫回来，左键/双击图标同理；
4. 「退出程序」只发 ``quitRequested`` 信号，不直接碰事件循环。
"""

import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QWindow

from backend import app_tray
from backend.app_tray import AppTrayController, install_app_tray
from tests.qt_test_utils import APP


ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = str(ROOT / "resources" / "app_icon.png")


class StubTray(QObject):
    """SystemTrayIcon 替身:记录菜单动作,保留 activated 信号与回调表。"""

    activated = Signal(int)

    def __init__(self):
        super().__init__()
        self._actions = []
        self._callbacks = {}
        self.shown = False

    def addAction(self, text, icon=None, shortcut="", triggered=None,  # noqa: N803
                  actionId="", **_extra):  # noqa: N803 - 与框架签名一致
        action_id = actionId or text
        self._actions.append({"text": text, "actionId": action_id})
        if triggered:
            self._callbacks[action_id] = triggered

    def addSeparator(self):  # noqa: N803
        self._actions.append({"separator": True})

    def actions(self):
        return list(self._actions)

    def show(self):
        self.shown = True

    def trigger(self, action_id):
        """复现用户点托盘菜单:框架把菜单项 actionId 回传给回调表。"""
        callback = self._callbacks.get(action_id)
        if callback is None:
            raise AssertionError(f"托盘菜单没有注册动作 {action_id}")
        callback()
        APP.processEvents()


class AppTrayDegradationTests(unittest.TestCase):
    def test_missing_window_skips_tray(self):
        self.assertIsNone(install_app_tray(None, ICON_PATH, "ConfigPilot"))

    def test_unavailable_system_tray_skips_tray(self):
        window = QWindow()
        self.addCleanup(window.destroy)
        with mock.patch.object(
            app_tray.SystemTrayIcon,
            "isSystemTrayAvailable",
            staticmethod(lambda: False),
        ):
            self.assertIsNone(install_app_tray(window, ICON_PATH, "ConfigPilot"))


class AppTrayControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = QWindow()
        self.window.setTitle("ConfigPilot 测试主窗")
        self.tray = StubTray()
        self.controller = AppTrayController(self.tray, self.window)
        self.addCleanup(self.window.destroy)

    def test_menu_has_show_then_separator_then_quit(self):
        self.assertEqual(self.controller.action_texts, ["显示主界面", "退出程序"])
        self.assertEqual(
            self.tray.actions(),
            [
                {"text": "显示主界面", "actionId": app_tray.SHOW_ACTION},
                {"separator": True},
                {"text": "退出程序", "actionId": app_tray.QUIT_ACTION},
            ],
        )
        self.assertTrue(self.tray.shown, "控制器没有把托盘图标显示出来")

    def test_show_action_brings_hidden_window_back(self):
        self.window.show()
        APP.processEvents()
        self.window.hide()
        APP.processEvents()
        self.assertFalse(self.window.isVisible())

        self.tray.trigger(app_tray.SHOW_ACTION)

        self.assertTrue(self.window.isVisible())

    def test_quit_action_only_emits_signal(self):
        fired = []
        self.controller.quitRequested.connect(lambda: fired.append(1))

        self.tray.trigger(app_tray.QUIT_ACTION)

        # 只发信号:真正结束进程由入口把 quitRequested 接到 QCoreApplication.quit()
        self.assertEqual(fired, [1])

    def test_left_click_on_icon_shows_window(self):
        from PySide6.QtWidgets import QSystemTrayIcon

        self.window.show()
        APP.processEvents()
        self.window.hide()
        APP.processEvents()

        reason = int(QSystemTrayIcon.ActivationReason.Trigger.value)
        self.tray.activated.emit(reason)
        APP.processEvents()

        self.assertTrue(self.window.isVisible())

    def test_right_click_does_not_reopen_window(self):
        from PySide6.QtWidgets import QSystemTrayIcon

        self.window.show()
        APP.processEvents()
        self.window.hide()
        APP.processEvents()

        reason = int(QSystemTrayIcon.ActivationReason.Context.value)
        self.tray.activated.emit(reason)
        APP.processEvents()

        self.assertFalse(self.window.isVisible(), "右键只该弹菜单，不该叫回窗口")


class RealSystemTrayTests(unittest.TestCase):
    """真托盘只在有通知区域的环境跑（offscreen 下自动跳过）。"""

    def test_install_creates_visible_tray(self):
        window = QWindow()
        self.addCleanup(window.destroy)
        controller = install_app_tray(window, ICON_PATH, "ConfigPilot")
        if controller is None:
            self.skipTest("当前系统没有可用的通知区域")
        self.assertEqual(controller.action_texts, ["显示主界面", "退出程序"])


if __name__ == "__main__":
    unittest.main()
