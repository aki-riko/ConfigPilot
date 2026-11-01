# coding: utf-8
"""关闭行为偏好（记住「最小化到托盘 / 退出程序」）的测试。

覆盖三件事：
1. 配置读写：默认 ask、损坏文件回落到 ask、原子写入、非法值收敛；
2. CloseBehaviorStore 的 QML 契约：closeBehavior 属性 + behaviorChanged 信号；
3. 重做后的对话框：勾选框存在、默认不勾、取消时不产生「记住」意图。
"""

import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from backend import close_behavior
from backend.close_behavior import (
    ASK,
    QUIT,
    TRAY,
    CloseBehaviorStore,
    load_close_behavior,
    normalize_behavior,
    resolve_close_behavior_path,
    save_close_behavior,
)
from tests.qt_test_utils import APP


ROOT = Path(__file__).resolve().parents[1]
DIALOG_DIR = ROOT / "qml" / "dialogs"


class CloseBehaviorFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "close_behavior.json"

    def test_missing_file_falls_back_to_ask(self):
        self.assertEqual(load_close_behavior(self.path), ASK)

    def test_roundtrip_each_behavior(self):
        for behavior in (TRAY, QUIT, ASK):
            save_close_behavior(self.path, behavior)
            self.assertEqual(load_close_behavior(self.path), behavior)

    def test_corrupt_file_falls_back_to_ask(self):
        for garbage in ("", "{", "[]", "null", '"tray"', '{"behavior": 42}'):
            self.path.write_text(garbage, encoding="utf-8")
            self.assertEqual(
                load_close_behavior(self.path), ASK,
                f"损坏内容 {garbage!r} 应回落到 ask",
            )

    def test_unknown_behavior_is_normalized_to_ask(self):
        self.path.write_text('{"behavior": "explode"}', encoding="utf-8")
        self.assertEqual(load_close_behavior(self.path), ASK)

    def test_save_writes_single_key_and_no_temp_left(self):
        save_close_behavior(self.path, TRAY)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data, {"behavior": TRAY})
        leftovers = [p.name for p in self.path.parent.iterdir()
                     if p.name != self.path.name]
        self.assertEqual(leftovers, [], "原子写入不该留下临时文件")

    def test_normalize_accepts_case_and_whitespace(self):
        self.assertEqual(normalize_behavior(" TRAY "), TRAY)
        self.assertEqual(normalize_behavior("Quit"), QUIT)
        self.assertEqual(normalize_behavior(None), ASK)

    def test_path_matches_documented_config_directory(self):
        path = resolve_close_behavior_path(
            platform_name="nt", environment={"LOCALAPPDATA": r"C:\local"}
        )
        self.assertEqual(path, Path(r"C:\local") / "ConfigPilot"
                         / "close_behavior.json")


class CloseBehaviorStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "close_behavior.json"

    def test_defaults_to_ask_and_exposes_property(self):
        store = CloseBehaviorStore(self.path)
        self.assertEqual(store.closeBehavior, ASK)
        self.assertEqual(store.behavior(), ASK)

    def test_set_behavior_persists_and_emits_once(self):
        store = CloseBehaviorStore(self.path)
        seen = []
        store.behaviorChanged.connect(lambda: seen.append(store.closeBehavior))

        store.setBehavior(TRAY)
        self.assertEqual(seen, [TRAY])
        self.assertEqual(load_close_behavior(self.path), TRAY)

        # 同值再设一次：不该再发信号（避免设置页反复写盘）
        store.setBehavior(TRAY)
        self.assertEqual(seen, [TRAY])

    def test_loads_existing_behavior_on_construction(self):
        save_close_behavior(self.path, QUIT)
        store = CloseBehaviorStore(self.path)
        self.assertEqual(store.closeBehavior, QUIT)

    def test_reset_to_ask(self):
        save_close_behavior(self.path, QUIT)
        store = CloseBehaviorStore(self.path)
        store.resetToAsk()
        self.assertEqual(store.closeBehavior, ASK)
        self.assertEqual(load_close_behavior(self.path), ASK)

    def test_write_failure_keeps_memory_state(self):
        """落盘失败不该让设置失效：内存里仍然按新档位工作。"""
        store = CloseBehaviorStore(self.path)

        def broken(*args, **kwargs):
            raise OSError("disk on fire")

        original = close_behavior.save_close_behavior
        close_behavior.save_close_behavior = broken
        try:
            store.setBehavior(QUIT)
        finally:
            close_behavior.save_close_behavior = original
        self.assertEqual(store.closeBehavior, QUIT)


class CloseChoiceRememberTests(unittest.TestCase):
    """重做后的对话框：勾选框存在且不改变既有的三出口契约。"""

    def setUp(self):
        self._kept = []

    def _create(self):
        import os

        import prismqml
        from prismqml import getThemeManager

        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        self._kept.append(getThemeManager())
        engine.rootContext().setContextProperty("ThemeManager", self._kept[-1])
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
        return dialog

    def _find(self, dialog, object_name):
        return next(
            (child for child in dialog.findChildren(QObject)
             if child.objectName() == object_name),
            None,
        )

    def test_checkbox_exists_and_defaults_unchecked(self):
        dialog = self._create()
        checkbox = self._find(dialog, "closeChoiceRememberCheckBox")
        self.assertIsNotNone(checkbox, "对话框缺少「记住我的选择」勾选框")
        self.assertFalse(bool(checkbox.property("checked")),
                         "勾选框默认必须是不勾的，不能悄悄改掉「每次询问」")
        self.assertFalse(bool(dialog.property("rememberChoice")))

    def test_remembered_behavior_empty_until_chosen(self):
        dialog = self._create()
        self.assertEqual(str(dialog.property("rememberedBehavior")), "")

    def test_remembered_behavior_follows_card_choice(self):
        dialog = self._create()
        dialog.setProperty("rememberChoice", True)

        dialog.setProperty("choice", "tray")
        self.assertEqual(str(dialog.property("rememberedBehavior")), "tray")

        dialog.setProperty("choice", "quit")
        self.assertEqual(str(dialog.property("rememberedBehavior")), "quit")

    def test_cancel_never_remembers(self):
        """勾着「记住」再点取消，不能把自己锁成「下次不问」。"""
        dialog = self._create()
        dialog.setProperty("rememberChoice", True)
        dialog.setProperty("choice", "cancel")
        self.assertEqual(str(dialog.property("rememberedBehavior")), "")

    def test_unchecked_choice_is_not_remembered(self):
        dialog = self._create()
        dialog.setProperty("choice", "quit")
        self.assertEqual(str(dialog.property("rememberedBehavior")), "")


if __name__ == "__main__":
    unittest.main()
