# coding: utf-8
"""``wire_api`` 通信协议下拉框的行为测试。

通信协议原先是自由文本框，可以填进 Codex 根本不认的值。改成下拉框后，
本文件用 offscreen 真实实例化 ``ConnectionSection.qml`` 验证：

1. 控件是 ComboBox（有 model / currentIndex / activated），不再是文本框；
2. 候选只有 Codex 接受的两种 OpenAI 线协议标识 ``responses`` 与 ``chat``；
3. 用户选择后按 ``wireApiEdited`` 回传该标识（草稿值，不直接写盘）；
4. 外部值变化会同步选中项；历史配置里的未知值原样追加显示，不被静默改写。
"""

import os
import unittest
from pathlib import Path

import prismqml
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QJSValue, QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from tests.qt_test_utils import APP


ROOT = Path(__file__).resolve().parents[1]
VIEWS_DIR = ROOT / "qml" / "views"


class StubCodexConfig(QObject):
    """下拉框本身不访问 CodexConfig，这里只提供 QML 里存在的全局名。"""


class WireApiComboBoxTests(unittest.TestCase):
    def setUp(self):
        # 保活 engine/component/对象，被 Python 回收后 QML 侧会读到 null
        self._kept = []

    def _create(self, wire_api_value=""):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        engine.rootContext().setContextProperty(
            "CodexConfig", StubCodexConfig()
        )
        component = QQmlComponent(engine)
        component.loadUrl(
            QUrl.fromLocalFile(str(VIEWS_DIR / "ConnectionSection.qml"))
        )
        self.assertFalse(
            component.isError(),
            "ConnectionSection.qml 加载失败: "
            + "; ".join(err.toString() for err in component.errors()),
        )
        root = component.create()
        self.assertIsNotNone(root)
        self._kept.extend([engine, component, root])
        root.setProperty("wireApiValue", wire_api_value)
        box = root.findChild(QQuickItem, "wireApiComboBox")
        self.assertIsNotNone(box, "找不到 objectName 为 wireApiComboBox 的控件")
        APP.processEvents()  # Component.onCompleted 里的 Qt.callLater 建表
        return root, box

    def _options(self, box):
        model = box.property("model")
        if isinstance(model, QJSValue):
            model = model.toVariant()
        self.assertIsInstance(model, list, "model 不是列表，控件不是下拉框")
        return model

    def _values(self, box):
        return [item["value"] for item in self._options(box)]

    def _texts(self, box):
        return [item["text"] for item in self._options(box)]

    def test_widget_is_a_combobox_with_two_protocol_options(self):
        root, box = self._create("responses")
        self.assertTrue(hasattr(box, "activated"), "控件缺少 activated 信号")
        self.assertIsNotNone(box.property("currentIndex"), "控件缺少 currentIndex")
        self.assertIsNone(
            root.findChild(QQuickItem, "wireApiEdit"),
            "旧的自由文本框仍然存在",
        )
        self.assertEqual(self._values(box), ["responses", "chat"])
        self.assertIn("Responses API", self._texts(box)[0])
        self.assertIn("Chat Completions API", self._texts(box)[1])
        self.assertEqual(box.property("currentIndex"), 0)

    def test_selecting_chat_emits_wire_api_draft_value(self):
        root, box = self._create("responses")
        emitted = []
        root.wireApiEdited.connect(lambda value: emitted.append(value))

        box.activated.emit(1)
        APP.processEvents()

        self.assertEqual(emitted, ["chat"])
        # 复现 CodexView 的草稿回写：界面值来自 wireApiValue，控件跟随选中
        root.setProperty("wireApiValue", emitted[-1])
        APP.processEvents()

        self.assertEqual(box.property("currentIndex"), 1)
        self.assertEqual(box.property("currentText"), self._texts(box)[1])

    def test_external_value_syncs_current_index(self):
        root, box = self._create("responses")
        self.assertEqual(box.property("currentIndex"), 0)

        root.setProperty("wireApiValue", "chat")
        APP.processEvents()

        self.assertEqual(box.property("currentIndex"), 1)

    def test_unknown_historical_value_is_kept_visible(self):
        root, box = self._create("responses")

        root.setProperty("wireApiValue", "responses-v2")
        APP.processEvents()

        self.assertEqual(
            self._values(box), ["responses", "chat", "responses-v2"]
        )
        self.assertEqual(box.property("currentIndex"), 2)
        self.assertIn("现有配置值", self._texts(box)[2])


if __name__ == "__main__":
    unittest.main()
