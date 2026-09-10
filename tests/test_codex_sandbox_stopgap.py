import tempfile
import tomllib
import unittest
from pathlib import Path

from backend.codex_config_store import SANDBOX_STOPGAP_MODE, CodexConfigStore


ORIGINAL_CONFIG = """model = "gpt-5.5"
model_provider = "relay"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
notify = ["cmd", "/c", "echo"]

[windows]
sandbox = "elevated"

[model_providers.relay]
name = "relay"
base_url = "https://api.example.com/v1"
wire_api = "responses"

[projects.'d:\\work']
trust_level = "trusted"

[features]
some_flag = true
"""


def write_config(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def load(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class SandboxStopgapTests(unittest.TestCase):
    def test_stopgap_writes_non_sandbox_mode_and_keeps_everything_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            write_config(config_path, ORIGINAL_CONFIG)
            store = CodexConfigStore(str(home))

            snapshot = store.apply_sandbox_stopgap()

            data = load(config_path)
            self.assertEqual(data["sandbox_mode"], SANDBOX_STOPGAP_MODE)
            self.assertEqual(data["approval_policy"], "on-request")
            self.assertEqual(data["model"], "gpt-5.5")
            self.assertEqual(data["windows"], {"sandbox": "elevated"})
            self.assertEqual(data["projects"]["d:\\work"]["trust_level"], "trusted")
            self.assertEqual(data["features"], {"some_flag": True})
            self.assertEqual(data["notify"], ["cmd", "/c", "echo"])
            self.assertEqual(
                data["model_providers"]["relay"]["base_url"],
                "https://api.example.com/v1",
            )
            self.assertEqual(snapshot["sandboxMode"], SANDBOX_STOPGAP_MODE)
            self.assertTrue(snapshot["hasRestorableChanges"])

    def test_stopgap_can_be_restored_by_managed_change_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            write_config(config_path, ORIGINAL_CONFIG)
            store = CodexConfigStore(str(home))

            store.apply_sandbox_stopgap()
            result = store.restore_managed_changes()

            self.assertEqual(result["restored"], 1)
            self.assertEqual(result["skipped"], 0)
            data = load(config_path)
            self.assertEqual(data["sandbox_mode"], "workspace-write")
            self.assertEqual(data["windows"], {"sandbox": "elevated"})
            self.assertEqual(data["approval_policy"], "on-request")
            self.assertEqual(result["snapshot"]["sandboxMode"], "workspace-write")

    def test_stopgap_does_not_overwrite_later_external_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            write_config(config_path, ORIGINAL_CONFIG)
            store = CodexConfigStore(str(home))

            store.apply_sandbox_stopgap()
            text = config_path.read_text(encoding="utf-8").replace(
                f'sandbox_mode = "{SANDBOX_STOPGAP_MODE}"',
                'sandbox_mode = "read-only"',
            )
            write_config(config_path, text)
            result = store.restore_managed_changes()

            self.assertEqual(result["restored"], 0)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(load(config_path)["sandbox_mode"], "read-only")

    def test_stopgap_adds_missing_sandbox_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            write_config(config_path, 'model = "gpt-5.5"\n')
            store = CodexConfigStore(str(home))

            snapshot = store.apply_sandbox_stopgap()

            data = load(config_path)
            self.assertEqual(data["sandbox_mode"], SANDBOX_STOPGAP_MODE)
            self.assertEqual(data["model"], "gpt-5.5")
            self.assertEqual(snapshot["sandboxMode"], SANDBOX_STOPGAP_MODE)

    def test_stopgap_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex"
            home.mkdir()
            config_path = home / "config.toml"
            write_config(config_path, ORIGINAL_CONFIG)
            store = CodexConfigStore(str(home))

            store.apply_sandbox_stopgap()
            applied_once = config_path.read_text(encoding="utf-8")
            store.apply_sandbox_stopgap()
            applied_twice = config_path.read_text(encoding="utf-8")

            self.assertEqual(applied_once, applied_twice)
            result = store.restore_managed_changes()
            self.assertEqual(result["restored"], 1)
            self.assertEqual(load(config_path)["sandbox_mode"], "workspace-write")


if __name__ == "__main__":
    unittest.main()
