# coding: utf-8
"""关闭主窗口的真实链路测试（qml/main.qml + CloseChoiceDialog + 托盘隐藏）。

这条链上每一环都只是"看起来对"就必然出事：WindowsCore 的
``closeRequested`` 要显式把 ``closeRequestAccepted`` 置 false 才能挡下这次关闭，
对话框只发信号不碰窗口，main.qml 才决定 hide 还是 quit。所以这里不读源码断言，
而是把 main.qml 真加载出来，用 ``window.close()`` 触发原生关闭请求，
再点对话框里的真实按钮，核对窗口可见性与 ``quitApproved`` 标志。

约定：关闭主窗口**不会**静默缩到托盘，也不会不问就退出。
"""

import importlib
import os
import tempfile
import unittest
from pathlib import Path

import prismqml
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from tests.qt_test_utils import APP, wait_for_idle


ROOT = Path(__file__).resolve().parents[1]
MAIN_QML = ROOT / "qml" / "main.qml"


class MainWindowCloseFlowTests(unittest.TestCase):
    def setUp(self):
        self._kept = []

    def _find(self, scope, object_name):
        return next(
            (child for child in scope.findChildren(QQuickItem)
             if child.objectName() == object_name),
            None,
        )

    def _load(self):
        engine = QQmlApplicationEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        from prismqml import register_types

        register_types(engine, config_path=None, persist_appearance=False)
        ctx = engine.rootContext()

        # 真实 CodexConfig，但把 .codex 指到临时目录：不读用户本机配置。
        codex_config = importlib.reload(
            importlib.import_module("backend.codex_config")
        )
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        codex_home = Path(tmp.name) / ".codex"
        codex_home.mkdir()
        codex_config._codex_home = lambda: str(codex_home)
        codex_config._app_dir = lambda: str(ROOT)
        codex = codex_config.CodexConfig()
        wait_for_idle(codex)
        self._kept.append(codex)

        ctx.setContextProperty("CodexConfig", codex)
        ctx.setContextProperty("ClaudeDesktopConfig", QObject())
        # 主窗口第一页是 Codex 页；桌宠与更新器不在本条链路上，给空壳即可。
        ctx.setContextProperty("PetManager", None)
        ctx.setContextProperty("NewApiPet", None)
        ctx.setContextProperty("PetStandalone", False)
        ctx.setContextProperty("AppAutoCheckEnabled", False)
        ctx.setContextProperty("AppUpdateStartupDelayMs", 1500)
        ctx.setContextProperty("AppInstallerSilentArgs", "/VERYSILENT")
        ctx.setContextProperty("AppUpdater", None)
        ctx.setContextProperty("appUpdater", None)
        ctx.setContextProperty("AppVersion", "0.0.0-test")
        ctx.setContextProperty("PrismQMLVersion", prismqml.__version__)
        ctx.setContextProperty("PrismQMLHomepage", "")
        ctx.setContextProperty("AppHomepage", "")
        ctx.setContextProperty("AppAuthor", "test")
        ctx.setContextProperty("AppYear", "2026")
        ctx.setContextProperty("AppLogo", "")
        ctx.setContextProperty("FluentIconsDir", "")

        engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
        self._pump(20)
        self.assertTrue(
            engine.rootObjects(),
            f"main.qml 加载失败: {MAIN_QML}",
        )
        root = engine.rootObjects()[0]
        self._kept.extend([engine, root])
        window = root.property("windowInstance")
        self.assertIsNotNone(window, "主窗口实例没创建出来")
        self._pump(60)
        return window

    def _pump(self, times=30):
        for _ in range(times):
            APP.processEvents()

    def _click(self, window, object_name):
        button = self._find(window, object_name)
        self.assertIsNotNone(button, f"找不到按钮 {object_name}")
        button.clicked.emit()
        self._pump(40)

    def test_close_asks_instead_of_hiding_to_tray(self):
        window = self._load()
        dialog = self._find(window, "closeChoiceDialog")
        self.assertIsNotNone(dialog, "主窗口没有挂上关闭选择对话框")
        self.assertTrue(bool(window.property("visible")))

        window.close()
        self._pump(30)

        self.assertTrue(bool(dialog.property("isOpen")),
                        "点关闭没有弹出选择框")
        # 只断言 isOpen 挡不住真实发生过的 BUG：Fluent.Windows 的默认属性是 pages
        # （页面列表）而不是 contentData，声明在窗口里的 CloseChoiceDialog 拿不到
        # 视觉父项 —— _isOpen 被置真，但节点不在场景树里，宽高 0、永远不可见，
        # 用户点关闭就是"什么都没发生"。所以必须核对它真的挂进了窗口并可见。
        self.assertIsNotNone(dialog.property("parent"),
                            "对话框没有视觉父项，根本没进窗口场景树")
        self.assertTrue(bool(dialog.property("visible")),
                        "对话框 _isOpen 为真但不可见：用户看不到任何反应")
        self.assertGreater(dialog.property("width"), 0,
                           "对话框宽度为 0，无法显示")
        self.assertGreater(dialog.property("height"), 0,
                           "对话框高度为 0，无法显示")
        self.assertTrue(bool(window.property("visible")),
                        "关闭请求没被挡下：窗口被直接关掉了")
        self.assertFalse(bool(window.property("quitApproved")),
                         "默认不该走退出")

    def test_tray_choice_hides_window_without_quitting(self):
        window = self._load()
        dialog = self._find(window, "closeChoiceDialog")
        window.close()
        self._pump(30)

        self._click(window, "closeChoiceTrayButton")

        self.assertEqual(str(dialog.property("choice")), "tray")
        self.assertFalse(bool(window.property("visible")),
                         "选「最小化到托盘」后窗口应该隐藏")
        self.assertFalse(bool(window.property("quitApproved")),
                         "隐藏到托盘不该被当成退出")

    def test_cancel_keeps_window_untouched(self):
        window = self._load()
        window.close()
        self._pump(30)

        self._click(window, "closeChoiceCancelButton")

        self.assertEqual(str(
            self._find(window, "closeChoiceDialog").property("choice")), "cancel")
        self.assertTrue(bool(window.property("visible")))
        self.assertFalse(bool(window.property("quitApproved")))

    def test_quit_choice_approves_quit_and_releases_second_close(self):
        window = self._load()
        window.close()
        self._pump(30)

        self._click(window, "closeChoiceQuitButton")

        self.assertTrue(bool(window.property("quitApproved")),
                        "选「退出程序」后必须放行后续关闭请求")
        # 已放行时再次收到关闭请求，不该再弹一次对话框
        dialog = self._find(window, "closeChoiceDialog")
        window.close()
        self._pump(30)
        self.assertFalse(bool(dialog.property("isOpen")),
                         "退出已获批准，关闭请求不该再问一遍")


if __name__ == "__main__":
    unittest.main()
