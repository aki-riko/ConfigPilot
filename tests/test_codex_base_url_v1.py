# coding: utf-8
"""Codex 地址自动补 ``/v1`` 的功能测试。

后端写入前规范化早就有了（v1.0.12），但界面上输入的地址要等「应用」回读后
才变成补全的样子，用户在此期间看到的仍是缺版本路径的地址。本文件锁定补齐后
的完整行为：

1. 后端 ``normalizedBaseUrl`` 暴露与写入一致的规范化；
2. ConnectionSection 地址框失焦/回车后真实回填（用 offscreen QML 实例化，
   触发真实 ``editingFinished``，不是读源码断言）。
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import prismqml
from PySide6.QtCore import QObject, Qt, QUrl, Slot
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from backend.endpoint_urls import normalize_v1_base_url
from tests.qt_test_utils import APP, wait_for_idle


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIEWS_DIR = ROOT / "qml" / "views"


class BackendNormalizeSlotTests(unittest.TestCase):
    """QML 侧调用的槽必须和 applyConfig 用同一套规则。"""

    def load_module(self):
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    def test_slot_matches_write_path_normalization(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            cases = {
                "https://api.9li.life": "https://api.9li.life/v1",
                "https://api.9li.life/": "https://api.9li.life/v1",
                "https://api.9li.life/v1": "https://api.9li.life/v1",
                "https://api.9li.life/v1/": "https://api.9li.life/v1",
                "https://example.test/openai": "https://example.test/openai/v1",
                "  ": "",
            }
            for typed, expected in cases.items():
                with self.subTest(typed=typed):
                    self.assertEqual(config.normalizedBaseUrl(typed), expected)
                    self.assertEqual(
                        config.normalizedBaseUrl(typed),
                        normalize_v1_base_url(typed),
                    )


class StubCodexConfig(QObject):
    """替身：把规范化直接委托给后端真实实现。"""

    @Slot(str, result=str)
    def normalizedBaseUrl(self, value):  # noqa: N802 - QML 公开名
        return normalize_v1_base_url(str(value or ""))


class BaseUrlFieldQmlTests(unittest.TestCase):
    def setUp(self):
        # 保活 engine/component/对象：被 Python 回收后 QML 侧会读到 null
        self._kept = []
        self._emitted = []

    def _create(self, *, with_config=True):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        if with_config:
            stub = StubCodexConfig()
            self._kept.append(stub)
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
        root.baseUrlEdited.connect(lambda value: self._emitted.append(value))
        field = root.findChild(QQuickItem, "baseUrlEdit")
        self.assertIsNotNone(field)
        APP.processEvents()  # Component.onCompleted 里的 Qt.callLater 回填
        return root, field

    def _finish_editing(self, field, typed):
        field.setProperty("text", typed)
        APP.processEvents()
        # editingFinished 的真实链路: LineEditNormal -> LineEditVariants 转发
        # -> LineEditCore.editingFinished (见 PrismQML 源码), 这里在核心信号上
        # 复现失焦/回车, 触发的是界面里那个 onEditingFinished 处理函数。
        field.editingFinished.emit()
        APP.processEvents()

    def _drafted(self):
        """界面最终交给 CodexView 的草稿地址（最后一次回传）。"""
        return self._emitted[-1] if self._emitted else None

    def test_missing_v1_is_completed_when_editing_finishes(self):
        root, field = self._create()
        root.setProperty("baseUrlValue", "https://old.example.com/v1")
        self._emitted.clear()

        self._finish_editing(field, "https://api.9li.life")

        self.assertEqual(field.property("text"), "https://api.9li.life/v1")
        self.assertEqual(self._drafted(), "https://api.9li.life/v1")

    def test_trailing_slash_and_whitespace_are_normalized(self):
        root, field = self._create()
        root.setProperty("baseUrlValue", "https://old.example.com/v1")
        self._emitted.clear()

        self._finish_editing(field, "  https://api.9li.life/  ")

        self.assertEqual(field.property("text"), "https://api.9li.life/v1")
        self.assertEqual(self._drafted(), "https://api.9li.life/v1")

    def test_existing_v1_is_not_duplicated(self):
        root, field = self._create()
        root.setProperty("baseUrlValue", "https://old.example.com/v1")
        self._emitted.clear()

        self._finish_editing(field, "https://api.9li.life/v1")

        self.assertEqual(field.property("text"), "https://api.9li.life/v1")
        self.assertEqual(self._drafted(), "https://api.9li.life/v1")

        self._finish_editing(field, "https://api.9li.life/v1")
        self.assertEqual(field.property("text"), "https://api.9li.life/v1")
        self.assertEqual(self._drafted(), "https://api.9li.life/v1")

    def test_custom_subpath_keeps_its_own_prefix(self):
        root, field = self._create()
        root.setProperty("baseUrlValue", "https://old.example.com/v1")

        self._finish_editing(field, "https://example.test/openai")

        self.assertEqual(field.property("text"), "https://example.test/openai/v1")

    def test_empty_field_is_trimmed_and_not_applied(self):
        root, field = self._create()
        root.setProperty("baseUrlValue", "https://api.9li.life/v1")
        self._emitted.clear()

        self._finish_editing(field, "   ")

        self.assertEqual(field.property("text"), "")
        # 空地址只会被记成"待应用"，应用按钮要求非空，不会写坏 config.toml
        self.assertEqual(self._drafted(), "")

    def test_without_backend_object_field_is_left_untouched(self):
        """没有 CodexConfig 上下文对象时不得抛错，只做原样回传。"""
        root, field = self._create(with_config=False)
        root.setProperty("baseUrlValue", "https://old.example.com/v1")
        self._emitted.clear()

        self._finish_editing(field, "https://api.9li.life")

        self.assertEqual(field.property("text"), "https://api.9li.life")
        self.assertEqual(self._drafted(), "https://api.9li.life")


class CodexPageEndToEndTests(unittest.TestCase):
    """真实 CodexConfig + 真实 CodexView：输入失焦 → 补全 → 应用写盘。"""

    def load_module(self):
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    def test_typed_address_is_completed_then_written(self):
        from PySide6.QtCore import QMetaObject

        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            kept = []
            engine = QQmlEngine()
            engine.addImportPath(os.path.dirname(prismqml.__file__))
            engine.rootContext().setContextProperty("CodexConfig", config)
            component = QQmlComponent(engine)
            component.loadUrl(QUrl.fromLocalFile(str(VIEWS_DIR / "CodexView.qml")))
            self.assertFalse(
                component.isError(),
                "CodexView.qml 加载失败: "
                + "; ".join(err.toString() for err in component.errors()),
            )
            view = component.create()
            self.assertIsNotNone(view)
            kept.extend([engine, component, view])
            APP.processEvents()

            field = view.findChild(QQuickItem, "baseUrlEdit")
            self.assertIsNotNone(field)
            field.setProperty("text", "https://api.9li.life")
            APP.processEvents()
            field.editingFinished.emit()
            APP.processEvents()

            self.assertEqual(field.property("text"), "https://api.9li.life/v1")
            self.assertTrue(bool(view.property("hasDraftChanges")))

            QMetaObject.invokeMethod(view, "applyDraft", Qt.DirectConnection)
            wait_for_idle(config)

            self.assertEqual(config.baseUrl, "https://api.9li.life/v1")
            written = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('base_url = "https://api.9li.life/v1"', written)
            self.assertEqual(field.property("text"), "https://api.9li.life/v1")


if __name__ == "__main__":
    unittest.main()
