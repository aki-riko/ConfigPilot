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
from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
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

    def _load(self, store=None, close_behavior=None):
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

        # 关闭行为偏好：默认不注册（QML 侧按 "ask" 处理，等价于重做前）；
        # 需要时注入假 store 或在构造时给定档位。
        if store is None and close_behavior is not None:
            store = _FakeStore(close_behavior)
        if store is not None:
            ctx.setContextProperty("CloseBehavior", store)
            self._kept.append(store)

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

    # ==================== 记住选择（不再弹窗） ====================

    def test_no_store_registered_keeps_asking(self):
        """没注册 CloseBehavior 时按 ask 处理：行为与重做前一致。"""
        window = self._load()
        self.assertEqual(str(window.property("closeBehavior")), "ask")

    def test_remembered_tray_hides_without_asking(self):
        """记住「最小化到托盘」后，点 ✕ 直接隐藏、不弹窗。"""
        window = self._load(close_behavior="tray")
        self.assertEqual(str(window.property("closeBehavior")), "tray")

        window.close()
        self._pump(30)

        dialog = self._find(window, "closeChoiceDialog")
        self.assertFalse(bool(dialog.property("isOpen")),
                         "已记住托盘，不该再弹三选一")
        self.assertFalse(bool(window.property("visible")),
                         "记住托盘后窗口应直接隐藏")
        self.assertFalse(bool(window.property("quitApproved")),
                         "隐藏到托盘不是退出")

    def test_remembered_quit_quits_without_asking(self):
        """记住「退出程序」后，点 ✕ 直接放行退出、不弹窗。"""
        window = self._load(close_behavior="quit")
        window.close()
        self._pump(30)

        dialog = self._find(window, "closeChoiceDialog")
        self.assertFalse(bool(dialog.property("isOpen")),
                         "已记住退出，不该再弹三选一")
        self.assertTrue(bool(window.property("quitApproved")),
                        "记住退出后必须放行关闭请求")

    def test_checking_remember_persists_choice(self):
        """勾上「记住我的选择」再选托盘：写进 store，下次不再问。"""
        store = _FakeStore()
        window = self._load(store=store)
        window.close()
        self._pump(30)

        dialog = self._find(window, "closeChoiceDialog")
        checkbox = self._find(window, "closeChoiceRememberCheckBox")
        self.assertIsNotNone(checkbox)
        checkbox.setProperty("checked", True)
        self._pump(10)
        self.assertTrue(bool(dialog.property("rememberChoice")))

        self._click(window, "closeChoiceTrayButton")

        self.assertEqual(store.closeBehavior, "tray",
                         "勾选后必须把选择写进配置")
        self.assertFalse(bool(window.property("visible")))

    def test_cancel_does_not_persist_even_when_checked(self):
        """勾着「记住」点取消：什么都不记，下次仍然询问。"""
        store = _FakeStore()
        window = self._load(store=store)
        window.close()
        self._pump(30)

        self._find(window, "closeChoiceRememberCheckBox").setProperty(
            "checked", True)
        self._pump(10)
        self._click(window, "closeChoiceCancelButton")

        self.assertEqual(store.closeBehavior, "ask",
                         "取消不该写进任何记住的选择")
        self.assertTrue(bool(window.property("visible")))

    def test_checking_remember_without_store_does_not_crash(self):
        """没注册 CloseBehavior 时勾选并选托盘：不能抛 ReferenceError。"""
        window = self._load()
        window.close()
        self._pump(30)

        self._find(window, "closeChoiceRememberCheckBox").setProperty(
            "checked", True)
        self._pump(10)
        self._click(window, "closeChoiceTrayButton")

        # 关键：动作照常完成（隐藏），没有因为缺 store 中断
        self.assertFalse(bool(window.property("visible")),
                         "缺 store 时勾选记住，托盘动作仍须生效")


class _FakeStore(QObject):
    """与 backend.close_behavior.CloseBehaviorStore 同契约的测试替身。"""

    behaviorChanged = Signal()

    def __init__(self, behavior="ask"):
        super().__init__()
        self._behavior = behavior
        self.writes = []

    def _get(self):
        return self._behavior

    closeBehavior = Property(str, _get, notify=behaviorChanged)

    @Slot(str)
    def setBehavior(self, behavior):  # noqa: N802 - 与 QML 契约一致
        behavior = str(behavior)
        if not behavior:
            behavior = "ask"
        self.writes.append(behavior)
        if behavior == self._behavior:
            return
        self._behavior = behavior
        self.behaviorChanged.emit()


if __name__ == "__main__":
    unittest.main()
