import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.codex_config_store import CodexConfigStore


class CodexRelayAuthTests(unittest.TestCase):
    def test_repair_relay_auth_uses_env_for_explicit_key_without_replacing_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            auth_path = codex_home / "auth.json"
            original_auth = {
                "auth_mode": "chatgpt",
                "tokens": {
                    "id_token": "id",
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "account_id": "account",
                },
            }
            auth_path.write_text(json.dumps(original_auth), encoding="utf-8")
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
            self.assertEqual(provider["env_key"], "OPENAI_API_KEY")
            self.assertFalse(provider["requires_openai_auth"])
            self.assertEqual(
                json.loads(auth_path.read_text(encoding="utf-8")), original_auth
            )
            self.assertEqual(
                persist_mock.call_args.args, ("OPENAI_API_KEY", "relay-key")
            )
            self.assertEqual(snapshot["authSource"], "environment")
            self.assertTrue(snapshot["envKeyPresent"])

    def test_repair_relay_auth_migrates_existing_auth_json_key_to_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            auth_path = codex_home / "auth.json"
            original_auth = {"OPENAI_API_KEY": "stored-key", "auth_mode": "apikey"}
            auth_path.write_text(json.dumps(original_auth), encoding="utf-8")
            config_path.write_text(
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n',
                encoding="utf-8",
            )
            store = CodexConfigStore(str(codex_home))

            def persist(name, value):
                os.environ[name] = value

            with patch.dict(os.environ, {}, clear=True), patch(
                "backend.codex_config_store.persist_user_environment",
                side_effect=persist,
            ) as persist_mock:
                snapshot = store.repair_relay_auth("")

            with config_path.open("rb") as handle:
                provider = tomllib.load(handle)["model_providers"]["relay"]
            self.assertEqual(provider["env_key"], "OPENAI_API_KEY")
            self.assertFalse(provider["requires_openai_auth"])
            self.assertEqual(
                json.loads(auth_path.read_text(encoding="utf-8")), original_auth
            )
            self.assertEqual(
                persist_mock.call_args.args, ("OPENAI_API_KEY", "stored-key")
            )
            self.assertEqual(snapshot["authSource"], "environment")
            self.assertTrue(snapshot["hasKey"])
            self.assertTrue(snapshot["envKeyPresent"])


if __name__ == "__main__":
    unittest.main()
