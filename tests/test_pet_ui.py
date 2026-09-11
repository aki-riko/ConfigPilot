# coding: utf-8
"""桌宠 QML 的真实加载测试。

静态文本断言抓不到"QML 语法/结构被改坏"这类问题(桌宠面板是嵌套层数最深的
QML 之一,曾经因为少一个大括号导致卡片内容被裁掉)。这里用替身数据把
PetWindow / PetPanel 真正实例化一次,并核对三种形态的窗口高度。
"""

import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PET_DIR = ROOT / "qml" / "pet"

from PySide6.QtCore import Property, QObject, QPoint, Qt, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


# 实例化 Window 需要 QGuiApplication(conftest.py 已保证平台与实例)
APP = QGuiApplication.instance()


def _collect(root, predicate, out):
    """递归收集 QQuickItem 子树中满足条件的节点。"""
    if predicate(root):
        out.append(root)
    for child in root.childItems():
        _collect(child, predicate, out)


class _QmlWarningCapture:
    """捕获 Qt 侧消息,用来断言交互过程中没有 QML 运行期警告。"""

    def __init__(self):
        self._messages = []
        self._previous = None

    def _handler(self, mode, context, message):
        self._messages.append(str(message))

    def __enter__(self):
        from PySide6.QtCore import qInstallMessageHandler

        self._previous = qInstallMessageHandler(self._handler)
        return self

    def __exit__(self, exc_type, exc, tb):
        from PySide6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(self._previous)
        return False

    def stop(self):
        if self._previous is not None:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(self._previous)
            self._previous = None
        # 有些 Qt 消息会带换行,拆开便于阅读
        return [line for message in self._messages for line in message.splitlines() if line.strip()]


def _capture_qml_warnings():
    return _QmlWarningCapture()


# 与 PetWindow.qml 里的布局常量保持一致
PANEL_PADDING = 8
SPRITE_SIZE = 120
CARD_TOP = PANEL_PADDING
DETAIL_CONTENT_HEIGHT = 322
BUBBLE_HEIGHT = 76
SPRITE_GAP = PANEL_PADDING * 2
SPRITE_TOP = CARD_TOP + DETAIL_CONTENT_HEIGHT + SPRITE_GAP
BUBBLE_SPRITE_TOP = CARD_TOP + BUBBLE_HEIGHT + PANEL_PADDING
EXPECTED_HEIGHTS = {
    "detail": SPRITE_TOP + PANEL_PADDING + SPRITE_SIZE + PANEL_PADDING,
    "bubble": BUBBLE_SPRITE_TOP + PANEL_PADDING + SPRITE_SIZE + PANEL_PADDING,
    "pet": PANEL_PADDING + SPRITE_SIZE + SPRITE_GAP,
}


class StubPet(QObject):
    """桌宠控制器的替身:提供 QML 需要的全部只读属性。"""

    usageChanged = Signal()
    logsChanged = Signal()
    statusChanged = Signal()
    configSaved = Signal()
    saveErrorChanged = Signal()
    usageBumped = Signal()
    sourcesChanged = Signal()

    @Property(bool, notify=statusChanged)
    def sourceReady(self): return True
    @Property(bool, notify=statusChanged)
    def hasError(self): return False
    @Property(bool, notify=usageChanged)
    def lowBalance(self): return False
    @Property(str, notify=usageChanged)
    def tokenName(self): return "Codex"
    @Property(str, notify=usageChanged)
    def balanceText(self): return "∞"
    @Property(str, notify=usageChanged)
    def grantedText(self): return "∞"
    @Property(str, notify=usageChanged)
    def usedText(self): return "¥13,605.24"
    @Property(str, notify=usageChanged)
    def todayText(self): return "今日已用 ¥267.86 · 608 次"
    @Property(str, notify=usageChanged)
    def todayAmountText(self): return "¥267.86"
    @Property(int, notify=usageChanged)
    def todayCount(self): return 608
    @Property(str, notify=usageChanged)
    def todayPromptTokensText(self): return "1.16B"
    @Property(str, notify=usageChanged)
    def todayCompletionTokensText(self): return "282K"
    @Property(str, notify=usageChanged)
    def todayTokensText(self): return "↑1.16B ↓282K"
    @Property(str, notify=usageChanged)
    def expiresText(self): return "永久有效"
    @Property(str, notify=statusChanged)
    def statusText(self): return "Codex 当前配置 · 每 60s 刷新 · 06:27:52"
    @Property("QVariantList", notify=logsChanged)
    def recentLogs(self):
        return [
            {"time": "09-12 06:25", "model": "gpt-5.6-sol",
             "tokens": "+54.8K / +309", "quotaText": "¥0.0634"},
            {"time": "09-12 06:25", "model": "gpt-5.6-sol",
             "tokens": "+59.3K / +112", "quotaText": "¥0.083"},
        ]
    @Property(str, notify=configSaved)
    def configPetImage(self): return ""
    @Property(int, notify=configSaved)
    def bubbleTimeoutSeconds(self): return 8
    @Property(int, notify=configSaved)
    def windowX(self): return -1
    @Property(int, notify=configSaved)
    def windowBottomY(self): return -1

    @Slot()
    def refresh(self): pass
    @Slot(int, int)
    def savePosition(self, x, y): pass


class PetQmlLoadTests(unittest.TestCase):
    def _engine(self):
        engine = QQmlEngine()
        # 必须保留替身引用:被 Python 回收后 QML 侧会读到 null
        self._stub = StubPet()
        engine.rootContext().setContextProperty("PetStandalone", True)
        engine.rootContext().setContextProperty("NewApiPet", self._stub)
        return engine

    def setUp(self):
        # 保活 component / 窗口:QQmlComponent 被回收会连带销毁它创建的窗口
        self._components = []
        self._objects = []

    def _create(self, engine, name):
        component = QQmlComponent(engine)
        component.loadUrl(QUrl.fromLocalFile(str(PET_DIR / name)))
        self.assertFalse(
            component.isError(),
            f"{name} 加载失败: " + "; ".join(err.toString() for err in component.errors()),
        )
        self._components.append(component)
        obj = component.create()
        self.assertIsNotNone(
            obj, f"{name} 实例化失败: "
                 + "; ".join(err.toString() for err in component.errors()),
        )
        self._objects.append(obj)
        return obj

    def test_pet_window_and_settings_dialog_instantiate(self):
        engine = self._engine()
        for name in ("PetWindow.qml", "PetSettingsDialog.qml"):
            with self.subTest(qml=name):
                self._create(engine, name)

    def test_pet_window_height_matches_panel_for_every_mode(self):
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        for mode, expected in EXPECTED_HEIGHTS.items():
            with self.subTest(mode=mode):
                window.setProperty("mode", mode)
                APP.processEvents()
                self.assertEqual(window.property("height"), expected)

    # ---------------------------------------------------------------- 交互链路

    def _mouse_area_in(self, parent):
        hits = []
        _collect(parent, lambda i: i.metaObject().className().startswith("QQuickMouseArea"), hits)
        return hits

    def _click(self, window, item, button=Qt.LeftButton):
        point = item.mapToScene(
            QPoint(int(item.width() / 2), int(item.height() / 2))
        ).toPoint()
        QTest.mouseClick(window, button, Qt.NoModifier, point)
        APP.processEvents()

    def test_pet_interactions_switch_modes_without_qml_errors(self):
        """点击气泡 / 收起 / 右键菜单都要真的切形态,且不能有 QML 运行期报错。

        形态与气泡计时器属于 PetWindow,面板只是画面;历史上把窗口级函数
        误挂到面板上,结果是点击时才抛 "is not a function" 的 QML 警告。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        captured = _capture_qml_warnings()
        try:
            panel = window.findChild(QQuickItem, "petPanel")
            self.assertIsNotNone(panel, "PetPanel 没有 objectName,无法定位")

            # 点击气泡 → 明细
            bubble_areas = self._mouse_area_in(panel.childItems()[1])
            self.assertTrue(bubble_areas, "气泡里没有 MouseArea")
            self._click(window, bubble_areas[0])
            self.assertEqual(window.property("mode"), "detail")

            # 收起 → 回到桌宠
            buttons = []
            _collect(panel, lambda i: i.metaObject().className().startswith("PetChipButton"), buttons)
            self.assertEqual(len(buttons), 2, "明细卡应该有刷新/收起两个按钮")
            self._click(window, buttons[1])
            self.assertEqual(window.property("mode"), "pet")

            # 悬停桌宠 → 弹气泡
            pet_area = next(
                (item for item in panel.childItems()
                 if item.metaObject().className().startswith("QQuickMouseArea") and item.z() == 10),
                None,
            )
            self.assertIsNotNone(pet_area, "没找到桌宠交互层")
            pet_point = pet_area.mapToScene(
                QPoint(int(pet_area.width() / 2), int(pet_area.height() / 2))
            ).toPoint()
            QTest.mouseMove(window, pet_point)
            APP.processEvents()
            self.assertEqual(window.property("mode"), "bubble")

            # 窗口刚变高,桌宠 hit 区会跟着上移:重新取一次坐标再右键,
            # 否则右键落在旧坐标(窗口外)上会被直接丢掉。
            pet_point = pet_area.mapToScene(
                QPoint(int(pet_area.width() / 2), int(pet_area.height() / 2))
            ).toPoint()
            QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, pet_point)
            APP.processEvents()
            menu = panel.findChild(QQuickItem, "petContextMenu")
            self.assertIsNotNone(menu, "右键菜单没有 objectName")
            self.assertTrue(menu.isVisible(), "右键菜单没打开")
            column = menu.childItems()[0]
            self._click(window, column.childItems()[1])
            self.assertEqual(window.property("mode"), "detail")
        finally:
            warnings = captured.stop()
        self.assertEqual(warnings, [], "交互过程中出现 QML 运行期警告: " + " | ".join(warnings))


if __name__ == "__main__":
    unittest.main()
