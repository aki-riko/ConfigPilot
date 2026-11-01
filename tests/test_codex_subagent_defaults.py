import tempfile
import tomllib
import unittest
from pathlib import Path

from backend.codex_config_store import CodexConfigStore


ROOT = Path(__file__).resolve().parents[1]


class SubagentDefaultsTests(unittest.TestCase):
    def test_writes_selected_model_and_preserves_other_config(self):
        original = '''model = "gpt-5.5"\nnotify = ["turn-ended"]\n\n[model_providers.relay]\nname = "relay"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(original, encoding="utf-8")

            snapshot = CodexConfigStore(str(home)).apply_subagent_defaults(
                "gpt-6-sol", "high"
            )

            with config_path.open("rb") as handle:
                data = tomllib.load(handle)
            self.assertEqual(
                data["agents"],
                {
                    "default_subagent_model": "gpt-6-sol",
                    "default_subagent_reasoning_effort": "high",
                },
            )
            self.assertEqual(data["model"], "gpt-5.5")
            self.assertEqual(data["notify"], ["turn-ended"])
            self.assertEqual(data["model_providers"]["relay"]["name"], "relay")
            self.assertTrue(snapshot["hasRestorableChanges"])
            # 回显字段要能读出刚写进去的值，供抽屉预选。
            self.assertEqual(snapshot["subagentModel"], "gpt-6-sol")
            self.assertEqual(snapshot["subagentReasoningEffort"], "high")

    def test_model_is_required(self):
        """不能再有内置兜底模型：没选模型就必须拒绝写入。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            original = 'model = "gpt-5.5"\n'
            config_path.write_text(original, encoding="utf-8")

            store = CodexConfigStore(str(home))
            for bad_model in ("", "   ", None):
                with self.assertRaises(ValueError):
                    store.apply_subagent_defaults(bad_model, "high")
            self.assertEqual(config_path.read_text(encoding="utf-8"), original)

    def test_blank_effort_removes_the_key(self):
        """空推理档表示移除该键，回落到 Codex 自身默认，而不是写一个空串。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text('model = "gpt-5.5"\n', encoding="utf-8")
            store = CodexConfigStore(str(home))

            store.apply_subagent_defaults("gpt-5.6-sol", "high")
            store.apply_subagent_defaults("gpt-5.6-sol", "")

            with config_path.open("rb") as handle:
                data = tomllib.load(handle)
            self.assertEqual(data["agents"], {"default_subagent_model": "gpt-5.6-sol"})

    def test_rejects_malformed_effort(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            original = 'model = "gpt-5.5"\n'
            config_path.write_text(original, encoding="utf-8")

            store = CodexConfigStore(str(home))
            with self.assertRaises(ValueError):
                store.apply_subagent_defaults("gpt-5.6-sol", 'high"\ninjected = 1')
            self.assertEqual(config_path.read_text(encoding="utf-8"), original)

    def test_is_idempotent_and_restorable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            original = 'model = "gpt-5.5"\n'
            config_path.write_text(original, encoding="utf-8")
            store = CodexConfigStore(str(home))

            store.apply_subagent_defaults("gpt-6-sol", "high")
            applied = config_path.read_text(encoding="utf-8")
            store.apply_subagent_defaults("gpt-6-sol", "high")
            self.assertEqual(config_path.read_text(encoding="utf-8"), applied)

            result = store.restore_managed_changes()
            self.assertEqual(result["restored"], 2)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(config_path.read_text(encoding="utf-8"), original)

    def test_external_change_is_not_overwritten_on_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text('model = "gpt-5.5"\n', encoding="utf-8")
            store = CodexConfigStore(str(home))

            store.apply_subagent_defaults("gpt-6-sol", "high")
            current = config_path.read_text(encoding="utf-8").replace(
                'default_subagent_model = "gpt-6-sol"',
                'default_subagent_model = "gpt-6-astra"',
            )
            config_path.write_text(current, encoding="utf-8")

            result = store.restore_managed_changes()
            self.assertEqual(result["restored"], 1)
            self.assertEqual(result["skipped"], 1)
            with config_path.open("rb") as handle:
                data = tomllib.load(handle)
            self.assertEqual(data["agents"]["default_subagent_model"], "gpt-6-astra")


class SubagentDefaultsUiTests(unittest.TestCase):
    def test_codex_page_exposes_named_repair_button_and_backend_slot(self):
        view = (ROOT / "qml" / "views" / "CodexView.qml").read_text(encoding="utf-8")
        toolbox = (ROOT / "qml" / "views" / "ToolboxDrawer.qml").read_text(
            encoding="utf-8"
        )
        config = (ROOT / "backend" / "codex_config.py").read_text(encoding="utf-8")
        store = (ROOT / "backend" / "codex_config_store.py").read_text(encoding="utf-8")
        # 「修复降智」已收进工具箱外抽屉，入口由抽屉转发到页面。
        self.assertIn("修复降智", toolbox)
        self.assertIn("signal repairSubagentDefaultsRequested(string model)", toolbox)
        self.assertIn("onRepairSubagentDefaultsRequested: function(model)", view)
        self.assertIn("CodexConfig.repairSubagentDefaults(model)", view)
        self.assertIn("def repairSubagentDefaults(self, model=", config)
        self.assertIn("self._store.apply_subagent_defaults", config)
        self.assertIn("def apply_subagent_defaults(self, model", store)

    def test_repair_requires_a_manually_selected_model(self):
        """防回流：不允许再回到「内置一个模型名一键写入」的写法。"""
        toolbox = (ROOT / "qml" / "views" / "ToolboxDrawer.qml").read_text(
            encoding="utf-8"
        )
        config = (ROOT / "backend" / "codex_config.py").read_text(encoding="utf-8")
        store = (ROOT / "backend" / "codex_config_store.py").read_text(encoding="utf-8")

        # 选项来源必须是「获取模型」的结果，且抽屉里要有获取入口。
        self.assertIn("model: root.availableModels", toolbox)
        self.assertIn("signal modelsFetchRequested()", toolbox)
        self.assertIn("onModelsFetchRequested", (ROOT / "qml" / "views" / "CodexView.qml").read_text(encoding="utf-8"))
        # 没选模型时执行按钮不可用。
        self.assertIn("enabled: root.selectedSubagentModel.length > 0", toolbox)
        # 后端与 store 都不许再潜伏硬编码模型名（只查带引号的字面量，
        # 注释里提到旧名字属于说明文字，不算回流）。
        for source in (config, store, toolbox):
            for hardcoded in ('"gpt-6-sol"', '"gpt-6-astra"'):
                self.assertNotIn(hardcoded, source)

    def test_backend_resolves_effort_from_the_selected_model(self):
        config = (ROOT / "backend" / "codex_config.py").read_text(encoding="utf-8")
        self.assertIn("effort = self.highestReasoningEffortForModel(model_name)", config)


if __name__ == "__main__":
    unittest.main()
