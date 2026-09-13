# coding: utf-8
"""关闭主窗口的三选一对话框行为测试。

背景：关闭主窗口原先可能被静默收进托盘（或反过来，一点 X 就退进程）。
现在必须问一句，且三个出口各自独立：退出程序 / 最小化到托盘 / 取消。
这里 offscreen 真实实例化 ``qml/dialogs/CloseChoiceDialog.qml``，
点真实按钮（发 ``clicked`` 信号，走的就是 onClicked 那条路径）验证：

1. 三个按钮都在，文案正确；
2. 「退出程序」发 ``quitRequested``、「最小化到托盘」发 ``trayRequested``；
3. 「取消」和按 Esc（reject）什么都不发，窗口不该被动到；
4. 每次点完对话框自己关闭，choice 是终值。
"""

import os
import unittest
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from tests.qt_test_utils import APP


ROOT = Path(__file__).resolve().parents[1]
DIALOG_DIR = ROOT / "qml" / "dialogs"


def register_prismqml_on_engine(engine):
    """与 tests/test_pet_ui.py 同一口径：补模块路径 + 注册 ThemeManager。"""
    import prismqml
    from prismqml import getThemeManager

    engine.addImportPath(os.path.dirname(prismqml.__file__))
    register_prismqml_on_engine._keepalive = getThemeManager()
    engine.rootContext().setContextProperty(
        "ThemeManager", register_prismqml_on_engine._keepalive
    )
    return engine


class CloseChoiceDialogTests(unittest.TestCase):
    def setUp(self):
        self._kept = []

    def _create(self):
        engine = register_prismqml_on_engine(QQmlEngine())
        component = QQmlComponent(engine)
        component.loadUrl(
            QUrl.fromLocalFile(str(DIALOG_DIR / "CloseChoiceDialog.qml"))
        )
        self.assertFalse(
            component.isError(),
            "CloseChoiceDialog.qml 加载失败: "
            + "; ".join(err.toString() for err in component.errors()),
        )
        dialog = component.create()
        self.assertIsNotNone(dialog)
        self._kept.extend([engine, component, dialog])
        events = []
        dialog.quitRequested.connect(lambda: events.append("quit"))
        dialog.trayRequested.connect(lambda: events.append("tray"))
        self._events = events
        return dialog

    def _button(self, dialog, object_name):
        found = next(
            (child for child in dialog.findChildren(QQuickItem)
             if child.objectName() == object_name),
            None,
        )
        self.assertIsNotNone(found, f"对话框缺少按钮 {object_name}")
        return found

    def _click(self, button):
        button.clicked.emit()
        APP.processEvents()

    def test_three_buttons_with_expected_labels(self):
        dialog = self._create()
        labels = {}
        for name in ("closeChoiceQuitButton", "closeChoiceTrayButton",
                     "closeChoiceCancelButton"):
            labels[name] = str(self._button(dialog, name).property("text"))
        self.assertEqual(
            labels,
            {
                "closeChoiceQuitButton": "退出程序",
                "closeChoiceTrayButton": "最小化到托盘",
                "closeChoiceCancelButton": "取消",
            },
        )

    def test_quit_button_emits_quit_and_closes(self):
        dialog = self._create()
        dialog.open()
        APP.processEvents()
        self.assertTrue(dialog.property("isOpen"))

        self._click(self._button(dialog, "closeChoiceQuitButton"))

        self.assertEqual(self._events, ["quit"])
        self.assertEqual(dialog.property("choice"), "quit")
        self.assertFalse(dialog.property("isOpen"))

    def test_tray_button_emits_tray_only(self):
        dialog = self._create()
        dialog.open()
        APP.processEvents()

        self._click(self._button(dialog, "closeChoiceTrayButton"))

        self.assertEqual(self._events, ["tray"])
        self.assertEqual(dialog.property("choice"), "tray")
        self.assertFalse(dialog.property("isOpen"))

    def test_cancel_and_dismiss_emit_nothing(self):
        dialog = self._create()
        dialog.open()
        APP.processEvents()
        self._click(self._button(dialog, "closeChoiceCancelButton"))
        self.assertEqual(self._events, [])
        self.assertEqual(dialog.property("choice"), "cancel")
        self.assertFalse(dialog.property("isOpen"))

        # 按 Esc / 点遮罩：等价于 reject，同样不能有任何退出或隐藏动作
        dialog.open()
        APP.processEvents()
        dialog.reject()
        APP.processEvents()
        self.assertEqual(self._events, [])
        self.assertEqual(dialog.property("choice"), "cancel")

    def test_dialog_does_not_touch_windows_itself(self):
        """对话框只发信号：组件树里不该出现任何窗口对象。"""
        dialog = self._create()
        self.assertEqual(
            [child for child in dialog.findChildren(QObject)
             if child.metaObject().className() == "QQuickWindow"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
