import importlib
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from backend.codex_config_store import CodexConfigStore, KEEP
from backend.codex_restore_state import STATE_FILE_NAME
from tests.qt_test_utils import wait_for_idle


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


INITIAL_CONFIG = '''\
model_provider = "openai"
model = "gpt-5.5"
model_reasoning_effort = "medium"
disable_response_storage = false
model_context_window = 100000
model_auto_compact_token_limit = 90000
tool_output_token_limit = 4000
notify = ["notify-tool", "turn-ended"]

[features]
multi_agent = true

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.example/v1"
wire_api = "responses"

[projects.'D:/Work/Alpha']
trust_level = "trusted"
'''


def managed_values(provider="relay"):
    return {
        "baseUrl": "https://gateway.example/v1",
        "provider": provider,
        "wireApi": "responses",
        "model": "gpt-5.6-sol",
        "requiresAuth": True,
        "reasoningEffort": "xhigh",
        "disableStorage": True,
        "contextWindow": 258400,
        "autoCompactLimit": 245000,
        "toolOutputLimit": 6000,
        "modelCatalogJson": KEEP,
    }


class CodexConfigStoreRestoreTests(unittest.TestCase):
    def test_restore_only_managed_fields_preserves_workspace_and_other_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
            store = CodexConfigStore(str(home))

            applied = store.apply_config(managed_values())
            self.assertTrue(applied["hasRestorableChanges"])
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n[projects.'D:/Work/AddedAfterApply']\n"
                    'trust_level = "trusted"\n'
                )

            result = store.restore_managed_changes()
            with config_path.open("rb") as handle:
                restored = tomllib.load(handle)

            self.assertGreater(result["restored"], 0)
            self.assertEqual(result["skipped"], 0)
            self.assertFalse(result["snapshot"]["hasRestorableChanges"])
            self.assertEqual(restored["model_provider"], "openai")
            self.assertEqual(restored["model"], "gpt-5.5")
            self.assertEqual(restored["model_reasoning_effort"], "medium")
            self.assertFalse(restored["disable_response_storage"])
            self.assertEqual(restored["model_context_window"], 100000)
            self.assertEqual(restored["model_auto_compact_token_limit"], 90000)
            self.assertEqual(restored["tool_output_token_limit"], 4000)
            self.assertEqual(restored["notify"], ["notify-tool", "turn-ended"])
            self.assertTrue(restored["features"]["multi_agent"])
            self.assertEqual(
                set(restored["projects"]),
                {"D:/Work/Alpha", "D:/Work/AddedAfterApply"},
            )
            self.assertNotIn("relay", restored["model_providers"])
            self.assertFalse((home / STATE_FILE_NAME).exists())

    def test_external_field_edit_is_kept_and_consumes_its_restore_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
            store = CodexConfigStore(str(home))
            store.apply_config(managed_values())

            current = config_path.read_text(encoding="utf-8")
            current = current.replace(
                'model = "gpt-5.6-sol"', 'model = "externally-selected-model"'
            )
            config_path.write_text(current, encoding="utf-8")

            result = store.restore_managed_changes()
            with config_path.open("rb") as handle:
                restored = tomllib.load(handle)

            self.assertEqual(result["skipped"], 1)
            self.assertEqual(restored["model"], "externally-selected-model")
            self.assertEqual(restored["model_provider"], "openai")
            self.assertFalse((home / STATE_FILE_NAME).exists())

    def test_later_external_value_becomes_baseline_when_app_applies_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
            store = CodexConfigStore(str(home))
            store.apply_config(managed_values())

            current = config_path.read_text(encoding="utf-8").replace(
                'model = "gpt-5.6-sol"', 'model = "external-baseline"'
            )
            config_path.write_text(current, encoding="utf-8")
            second_values = managed_values()
            second_values["model"] = "gpt-5.6-terra"
            store.apply_config(second_values)
            store.restore_managed_changes()

            with config_path.open("rb") as handle:
                restored = tomllib.load(handle)
            self.assertEqual(restored["model"], "external-baseline")

    def test_auth_is_restored_only_while_it_matches_app_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            auth_path = home / "auth.json"
            original = '{"auth_mode":"chatgpt","access_token":"original-token"}\n'
            auth_path.write_text(original, encoding="utf-8")
            store = CodexConfigStore(str(home))

            store.set_key("configpilot-key")
            restored = store.restore_managed_changes()
            self.assertEqual(restored["restored"], 1)
            self.assertEqual(auth_path.read_text(encoding="utf-8"), original)

            store.set_key("second-configpilot-key")
            external = {"OPENAI_API_KEY": "external-key", "auth_mode": "apikey"}
            auth_path.write_text(json.dumps(external), encoding="utf-8")
            skipped = store.restore_managed_changes()
            self.assertEqual(skipped["skipped"], 1)
            self.assertEqual(
                json.loads(auth_path.read_text(encoding="utf-8")), external
            )

    def test_auth_created_by_app_is_removed_on_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            auth_path = home / "auth.json"
            store = CodexConfigStore(str(home))

            store.set_key("configpilot-key")
            self.assertTrue(auth_path.exists())
            store.restore_managed_changes()
            self.assertFalse(auth_path.exists())
            self.assertTrue((home / "auth.json.bak").exists())

    def test_no_restore_record_does_not_write_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
            before = config_path.read_bytes()

            result = CodexConfigStore(str(home)).restore_managed_changes()

            self.assertEqual(result["restored"], 0)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(config_path.read_bytes(), before)


class CodexConfigRestoreUiTests(unittest.TestCase):
    def load_module(self):
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    def test_async_restore_updates_availability_and_notifies(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
            codex_config._codex_home = lambda: str(home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.applyConfig(
                {
                    "baseUrl": "https://gateway.example",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                }
            )
            wait_for_idle(config)
            self.assertTrue(config.hasRestorableChanges)

            config.restoreInitialSettings()
            wait_for_idle(config)
            self.assertFalse(config.hasRestorableChanges)
            self.assertTrue(
                any(title == "已恢复初始设置" for _, title, _ in notices)
            )

    def test_qml_has_guarded_restore_confirmation(self):
        view = (ROOT / "qml" / "views" / "CodexView.qml").read_text(
            encoding="utf-8"
        )
        # 「恢复初始设置」已收进工具箱外抽屉，入口由抽屉转发，危险操作仍走确认框。
        toolbox = (ROOT / "qml" / "views" / "ToolboxDrawer.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn('objectName: "codexToolboxButton"', view)
        self.assertIn("signal restoreInitialRequested()", toolbox)
        self.assertIn("onRestoreInitialRequested", view)
        self.assertIn("CodexConfig.hasRestorableChanges", view)
        self.assertIn("Fluent.ConfirmDialog", view)
        self.assertIn("CodexConfig.restoreInitialSettings()", view)
        self.assertIn("[projects.*]", view)


if __name__ == "__main__":
    unittest.main()
