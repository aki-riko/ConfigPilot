import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.codex_config_store import CodexConfigStore


class CodexRelayAuthTests(unittest.TestCase):
    def test_repair_relay_auth_writes_env_key_and_syncs_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            config_path.write_text(
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n'
                'requires_openai_auth = true\n',
                encoding="utf-8",
            )
            store = CodexConfigStore(str(codex_home))

            def persist(name, value):
                os.environ[name] = value

            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch(
                "backend.codex_config_store.persist_user_environment",
                side_effect=persist,
            ) as persist_mock:
                snapshot = store.repair_relay_auth("relay-key")

            with config_path.open("rb") as handle:
                provider = tomllib.load(handle)["model_providers"]["relay"]
            auth = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
            self.assertEqual(provider["env_key"], "OPENAI_API_KEY")
            self.assertFalse(provider["requires_openai_auth"])
            self.assertEqual(auth["OPENAI_API_KEY"], "relay-key")
            self.assertEqual(
                persist_mock.call_args.args, ("OPENAI_API_KEY", "relay-key")
            )
            self.assertEqual(snapshot["authSource"], "environment")
            self.assertTrue(snapshot["envKeyPresent"])


if __name__ == "__main__":
    unittest.main()
