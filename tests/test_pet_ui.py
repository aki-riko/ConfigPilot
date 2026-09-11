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

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402


# 实例化 Window 需要 QGuiApplication(conftest.py 已保证平台与实例)
APP = QGuiApplication.instance()


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


if __name__ == "__main__":
    unittest.main()
