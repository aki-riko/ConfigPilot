import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummySignal:
    def __init__(self, *args, **kwargs):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args)


class DummyQObject:
    def __init__(self, parent=None):
        pass


def dummy_slot(*args, **kwargs):
    def decorate(func):
        return func

    return decorate


def dummy_property(*args, **kwargs):
    def decorate(func):
        return property(func)

    return decorate


def install_pyside_stub():
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = DummyQObject
    qtcore.Signal = DummySignal
    qtcore.Slot = dummy_slot
    qtcore.Property = dummy_property

    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore

    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore


class CodexConfigAuthTests(unittest.TestCase):
    def load_module(self):
        install_pyside_stub()
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    def test_set_key_moves_old_auth_to_backup_and_writes_clean_auth(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex_home = tmp_path / ".codex"
            codex_home.mkdir()
            old_auth = {
                "OPENAI_API_KEY": "old-key",
                "auth_mode": "chatgpt",
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
            }
            auth_path = codex_home / "auth.json"
            auth_path.write_text(json.dumps(old_auth), encoding="utf-8")

            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(tmp_path)

            config = codex_config.CodexConfig()
            config.setKey("new-key")

            new_auth = json.loads(auth_path.read_text(encoding="utf-8"))
            backup_auth = json.loads((codex_home / "auth.json.bak").read_text(encoding="utf-8"))

            self.assertEqual(
                new_auth,
                {
                    "OPENAI_API_KEY": "new-key",
                    "auth_mode": "apikey",
                },
            )
            self.assertEqual(backup_auth, old_auth)
            self.assertNotIn("access_token", new_auth)
            self.assertNotIn("refresh_token", new_auth)


if __name__ == "__main__":
    unittest.main()
