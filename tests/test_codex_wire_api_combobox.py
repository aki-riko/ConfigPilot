# coding: utf-8
"""``wire_api`` 通信协议下拉框的行为测试。

原先是自由文本框，可以填进 Codex 根本不认的值；改成下拉框后，界面上只显示
协议名（Responses API / Chat Completions API（已废弃）），写入 config.toml
的 ``responses`` / ``chat`` 标识由 ``backend/wire_api.py`` 统一映射。

本文件覆盖两层：

1. 后端映射表：显示名/端点/标识都能映射回写入值，认不出的历史值原样透传；
2. offscreen 真实实例化 ``ConnectionSection.qml``：下拉框不再露出最终标识，
   选择后回传显示名，经后端映射得到草稿里的 ``wire_api`` 值。
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import prismqml
from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtQml import QJSValue, QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from backend import wire_api
from tests.qt_test_utils import APP, wait_for_idle


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIEWS_DIR = ROOT / "qml" / "views"


def _to_python(value):
    """QML 的 var 属性在 PySide6 侧可能是 QJSValue。"""
    if isinstance(value, QJSValue):
        return value.toVariant()
    return value


class WireApiMappingTests(unittest.TestCase):
    """后端映射表：界面显示名 ↔ 写入 config.toml 的标识。"""

    def test_options_expose_display_names_and_write_values(self):
        options = wire_api.option_list()
        self.assertEqual(
            [option["value"] for option in options], ["responses", "chat"]
        )
        self.assertEqual(
            [option["text"] for option in options],
            ["Responses API", "Chat Completions API（已废弃）"],
        )
        self.assertTrue(options[1]["deprecated"])
        self.assertFalse(options[0]["deprecated"])

    def test_labels_map_to_display_names(self):
        self.assertEqual(wire_api.display_label("responses"), "Responses API")
        self.assertEqual(
            wire_api.display_label("chat"), "Chat Completions API（已废弃）"
        )
        self.assertNotEqual(wire_api.display_label("chat"), "chat")

    def test_canonical_value_maps_every_surface_form(self):
        cases = {
            "responses": "responses",
            "Responses API": "responses",
            "/v1/responses": "responses",
            "RESPONSES": "responses",
            "chat": "chat",
            "Chat Completions API": "chat",
            "Chat Completions API（已废弃）": "chat",
            "/v1/chat/completions": "chat",
            "  chat  ": "chat",
            "": "",
        }
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(wire_api.canonical_value(given), expected)

    def test_unknown_historical_value_passes_through(self):
        self.assertEqual(
            wire_api.canonical_value("responses-v2"), "responses-v2"
        )
        self.assertEqual(wire_api.display_label("responses-v2"), "responses-v2")


class StubCodexConfig(QObject):
    """替身：把映射直接委托给后端真实实现，界面测试不另算一套。"""

    @Slot(result="QVariantList")
    def wireApiOptions(self):  # noqa: N802 - QML 公开名
        return wire_api.option_list()

    @Slot(str, result=str)
    def wireApiLabel(self, value):  # noqa: N802 - QML 公开名
        return wire_api.display_label(value)

    @Slot(str, result=str)
    def wireApiValueFor(self, name):  # noqa: N802 - QML 公开名
        return wire_api.canonical_value(name)


class WireApiComboBoxTests(unittest.TestCase):
    def setUp(self):
        # 保活 engine/component/对象，被 Python 回收后 QML 侧会读到 null
        self._kept = []

    def _create(self, wire_api_value=""):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        stub = StubCodexConfig()
        self._kept.append(stub)  # 被 Python 回收后 QML 侧的 CodexConfig 会变成 null
        engine.rootContext().setContextProperty("CodexConfig", stub)
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
        model = _to_python(box.property("model"))
        self.assertIsInstance(model, list, "model 不是列表，控件不是下拉框")
        return model

    def _values(self, box):
        return [item["value"] for item in self._options(box)]

    def _texts(self, box):
        return [item["text"] for item in self._options(box)]

    def test_widget_is_a_combobox_showing_protocol_names(self):
        root, box = self._create("responses")
        self.assertTrue(hasattr(box, "activated"), "控件缺少 activated 信号")
        self.assertIsNotNone(box.property("currentIndex"), "控件缺少 currentIndex")
        self.assertIsNone(
            root.findChild(QQuickItem, "wireApiEdit"),
            "旧的自由文本框仍然存在",
        )
        self.assertEqual(self._values(box), ["responses", "chat"])
        self.assertEqual(
            self._texts(box),
            ["Responses API", "Chat Completions API（已废弃）"],
        )
        self.assertEqual(box.property("currentIndex"), 0)
        self.assertEqual(
            box.property("currentText"), "Responses API"
        )

    def test_selecting_deprecated_protocol_maps_to_chat(self):
        root, box = self._create("responses")
        emitted = []
        root.wireApiEdited.connect(lambda value: emitted.append(value))

        box.activated.emit(1)
        APP.processEvents()

        # 界面回传的是显示名，最终标识由后端映射
        self.assertEqual(emitted, ["Chat Completions API（已废弃）"])
        self.assertEqual(wire_api.canonical_value(emitted[-1]), "chat")

        root.setProperty("wireApiValue", wire_api.canonical_value(emitted[-1]))
        APP.processEvents()

        self.assertEqual(box.property("currentIndex"), 1)
        self.assertEqual(
            box.property("currentText"), "Chat Completions API（已废弃）"
        )

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
        self.assertEqual(self._texts(box)[2], "responses-v2")


class CodexConfigWireApiSlotsTests(unittest.TestCase):
    """真实 CodexConfig 暴露给 QML 的三个槽必须和映射表一致。"""

    def test_slots_delegate_to_mapping(self):
        sys.modules.pop("backend.codex_config", None)
        codex_config = importlib.import_module("backend.codex_config")
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            options = _to_python(config.wireApiOptions())
            self.assertEqual(
                [option["text"] for option in options],
                ["Responses API", "Chat Completions API（已废弃）"],
            )
            self.assertEqual(
                config.wireApiLabel("chat"), "Chat Completions API（已废弃）"
            )
            self.assertEqual(
                config.wireApiValueFor("Chat Completions API（已废弃）"), "chat"
            )
            self.assertEqual(config.wireApiValueFor("Responses API"), "responses")


if __name__ == "__main__":
    unittest.main()
