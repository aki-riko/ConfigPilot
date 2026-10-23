# coding: utf-8
"""macOS/Linux 上把 env_key 认证落到 ``$CODEX_HOME/.env`` 的行为。

背景：Windows 有 HKCU\\Environment，进程外启动的 Codex 能继承；macOS 的 GUI
进程不读 ``~/.zshrc``，``launchctl setenv`` 也只活到注销。旧实现非 Windows 直接
return，于是「修复中转站 401」写好了 config.toml 的 env_key，却没有任何地方放
key，Codex 启动后报 ``Missing environment variable: `OPENAI_API_KEY```。
Codex 自己会在 arg0 初始化时用 dotenvy 读 ``$CODEX_HOME/.env``，这里就是那条路。
"""

import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.codex_config_store import (
    CodexConfigStore,
    format_dotenv_value,
    parse_dotenv_values,
)


class DotenvParsingTests(unittest.TestCase):
    def test_parses_plain_quoted_and_commented_lines(self):
        values = parse_dotenv_values(
            "# 注释\n"
            "OPENAI_API_KEY=sk-plain\n"
            "export QUOTED=\"sk with space\"\n"
            "SINGLE='sk $literal'\n"
            "TRAILING=value # 行尾注释\n"
            "\n"
            "NOT_A_PAIR\n"
        )
        self.assertEqual(values["OPENAI_API_KEY"], "sk-plain")
        self.assertEqual(values["QUOTED"], "sk with space")
        self.assertEqual(values["SINGLE"], "sk $literal")
        self.assertEqual(values["TRAILING"], "value")
        self.assertNotIn("NOT_A_PAIR", values)

    def test_round_trips_values_needing_quotes(self):
        for raw in ("sk-simple", "sk with space", 'has"quote', "has#hash", "a\\b"):
            rendered = format_dotenv_value(raw)
            parsed = parse_dotenv_values(f"KEY={rendered}\n")
            self.assertEqual(parsed["KEY"], raw, f"{raw!r} -> {rendered!r}")


class NonWindowsDotenvTests(unittest.TestCase):
    def _store(self, tmp):
        codex_home = Path(tmp) / ".codex"
        codex_home.mkdir()
        return codex_home, CodexConfigStore(str(codex_home))

    def _write_config(self, codex_home, body):
        (codex_home / "config.toml").write_text(body, encoding="utf-8")

    def test_persisted_user_environment_supported_follows_os_name(self):
        from backend.codex_config_store import persisted_user_environment_supported

        with patch("backend.codex_config_store.os.name", "posix"):
            self.assertFalse(persisted_user_environment_supported())
        with patch("backend.codex_config_store.os.name", "nt"):
            self.assertTrue(persisted_user_environment_supported())

    def test_repair_relay_auth_writes_dotenv_when_platform_cannot_persist_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n'
                "requires_openai_auth = true\n",
            )
            with patch(
                "backend.codex_config_store.persisted_user_environment_supported",
                return_value=False,
            ), patch.dict(os.environ, {}, clear=True):
                snapshot = store.repair_relay_auth("relay-key")

            dotenv_path = codex_home / ".env"
            self.assertTrue(dotenv_path.is_file(), "macOS 必须把 key 落到 .env")
            self.assertEqual(
                parse_dotenv_values(dotenv_path.read_text(encoding="utf-8"))[
                    "OPENAI_API_KEY"
                ],
                "relay-key",
            )
            if os.name != "nt":
                self.assertEqual(
                    oct(dotenv_path.stat().st_mode & 0o777), oct(0o600)
                )
            with (codex_home / "config.toml").open("rb") as handle:
                provider = tomllib.load(handle)["model_providers"]["relay"]
            self.assertEqual(provider["env_key"], "OPENAI_API_KEY")
            self.assertFalse(provider["requires_openai_auth"])
            self.assertEqual(snapshot["authSource"], "environment")
            self.assertTrue(snapshot["envKeyPresent"])
            self.assertEqual(snapshot["envKeySource"], "dotenv")

    def test_dotenv_key_is_visible_to_provider_auth_for_model_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n'
                'env_key = "OPENAI_API_KEY"\n',
            )
            store.write_dotenv_key("OPENAI_API_KEY", "from-dotenv")
            with patch.dict(os.environ, {}, clear=True):
                auth = store.read_provider_auth()
            self.assertEqual(auth["source"], "environment")
            self.assertEqual(auth["key"], "from-dotenv")
            self.assertTrue(auth["ready"])

    def test_dotenv_wins_over_process_env_like_codex_set_var(self):
        """Codex 用 dotenvy 解析后无条件 set_var，因此 .env 覆盖进程环境。"""
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n'
                'env_key = "OPENAI_API_KEY"\n',
            )
            store.write_dotenv_key("OPENAI_API_KEY", "from-dotenv")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "from-process"}):
                auth = store.read_provider_auth()
            self.assertEqual(auth["key"], "from-dotenv")

    def test_write_dotenv_key_keeps_other_lines_and_replaces_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            dotenv_path = codex_home / ".env"
            dotenv_path.write_text(
                "# 用户自己的变量\nOTHER_VAR=keep-me\nOPENAI_API_KEY=old\n",
                encoding="utf-8",
            )
            store.write_dotenv_key("OPENAI_API_KEY", "new-key")
            text = dotenv_path.read_text(encoding="utf-8")
            values = parse_dotenv_values(text)
            self.assertEqual(values["OTHER_VAR"], "keep-me")
            self.assertEqual(values["OPENAI_API_KEY"], "new-key")
            self.assertIn("# 用户自己的变量", text)
            self.assertEqual(text.count("OPENAI_API_KEY="), 1)

    def test_restore_reverts_dotenv_created_by_configpilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n',
            )
            with patch(
                "backend.codex_config_store.persisted_user_environment_supported",
                return_value=False,
            ), patch.dict(os.environ, {}, clear=True):
                store.repair_relay_auth("relay-key")
                self.assertTrue((codex_home / ".env").is_file())
                result = store.restore_managed_changes()

            self.assertFalse(
                (codex_home / ".env").is_file(),
                "恢复初始设置应删掉 ConfigPilot 新建的 .env",
            )
            self.assertGreaterEqual(result["restored"], 1)

    def test_restore_keeps_preexisting_dotenv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n',
            )
            dotenv_path = codex_home / ".env"
            dotenv_path.write_text("OTHER_VAR=keep-me\n", encoding="utf-8")
            with patch(
                "backend.codex_config_store.persisted_user_environment_supported",
                return_value=False,
            ), patch.dict(os.environ, {}, clear=True):
                store.repair_relay_auth("relay-key")
                store.restore_managed_changes()

            values = parse_dotenv_values(dotenv_path.read_text(encoding="utf-8"))
            self.assertEqual(values["OTHER_VAR"], "keep-me")
            self.assertNotIn("OPENAI_API_KEY", values)

    def test_windows_path_does_not_touch_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, store = self._store(tmp)
            self._write_config(
                codex_home,
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'base_url = "https://gateway.example.com/v1"\n',
            )

            def persist(name, value):
                os.environ[name] = value

            with patch(
                "backend.codex_config_store.persisted_user_environment_supported",
                return_value=True,
            ), patch(
                "backend.codex_config_store.persist_user_environment",
                side_effect=persist,
            ), patch.dict(os.environ, {}, clear=True):
                store.repair_relay_auth("relay-key")

            self.assertFalse((codex_home / ".env").exists())


if __name__ == "__main__":
    unittest.main()
