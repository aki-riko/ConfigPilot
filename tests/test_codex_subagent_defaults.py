import tempfile
import tomllib
import unittest
from pathlib import Path

from backend.codex_config_store import CodexConfigStore


ROOT = Path(__file__).resolve().parents[1]


class SubagentDefaultsTests(unittest.TestCase):
    def test_writes_defaults_and_preserves_other_config(self):
        original = '''model = "gpt-5.5"\nnotify = ["turn-ended"]\n\n[model_providers.relay]\nname = "relay"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(original, encoding="utf-8")

            snapshot = CodexConfigStore(str(home)).apply_subagent_defaults()

            with config_path.open("rb") as handle:
                data = tomllib.load(handle)
            self.assertEqual(
                data["agents"],
                {
                    "default_subagent_model": "gpt-5.6-sol",
                    "default_subagent_reasoning_effort": "high",
                },
            )
            self.assertEqual(data["model"], "gpt-5.5")
            self.assertEqual(data["notify"], ["turn-ended"])
            self.assertEqual(data["model_providers"]["relay"]["name"], "relay")
            self.assertTrue(snapshot["hasRestorableChanges"])

    def test_is_idempotent_and_restorable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            original = 'model = "gpt-5.5"\n'
            config_path.write_text(original, encoding="utf-8")
            store = CodexConfigStore(str(home))

            store.apply_subagent_defaults()
            applied = config_path.read_text(encoding="utf-8")
            store.apply_subagent_defaults()
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

            store.apply_subagent_defaults()
            current = config_path.read_text(encoding="utf-8").replace(
                'default_subagent_model = "gpt-5.6-sol"',
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
        config = (ROOT / "backend" / "codex_config.py").read_text(encoding="utf-8")
        store = (ROOT / "backend" / "codex_config_store.py").read_text(encoding="utf-8")
        self.assertIn('objectName: "repairSubagentDefaultsButton"', view)
        self.assertIn('text: "修复降智"', view)
        self.assertIn("CodexConfig.repairSubagentDefaults()", view)
        self.assertIn("def repairSubagentDefaults(self)", config)
        self.assertIn("self._store.apply_subagent_defaults", config)
        self.assertIn("def apply_subagent_defaults(self)", store)


if __name__ == "__main__":
    unittest.main()
