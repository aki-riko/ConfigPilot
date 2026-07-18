import importlib
import json
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QTimer

from backend.codex_config_store import CodexConfigStore, KEEP
from tests.qt_test_utils import wait_for_idle, wait_until


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class CodexConfigAuthTests(unittest.TestCase):
    def load_module(self):
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    @staticmethod
    def store_values(provider="relay"):
        return {
            "baseUrl": "https://gateway.example.com/v1",
            "provider": provider,
            "wireApi": "responses",
            "model": "gpt-5.6-sol",
            "requiresAuth": None,
            "reasoningEffort": None,
            "disableStorage": None,
            "contextWindow": KEEP,
            "autoCompactLimit": KEEP,
            "toolOutputLimit": KEEP,
            "modelCatalogJson": KEEP,
        }

    def test_config_exists_is_cached_from_background_snapshot(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            with patch.object(
                codex_config.os.path,
                "isfile",
                side_effect=AssertionError("GUI 属性不应访问文件系统"),
            ):
                self.assertFalse(config.configExists)

            config.applyConfig(
                {
                    "baseUrl": "https://gateway.example.com",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                }
            )
            wait_for_idle(config)
            self.assertTrue(config.configExists)

    def test_slow_presets_read_does_not_block_gui_thread(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            timer_fired = []

            def slow_read():
                time.sleep(0.2)
                return []

            with patch.object(config, "_read_presets", side_effect=slow_read):
                QTimer.singleShot(10, lambda: timer_fired.append(True))
                started = time.perf_counter()
                config.reloadPresets()
                call_elapsed = time.perf_counter() - started
                wait_until(lambda: bool(timer_fired), timeout=0.15)
                self.assertTrue(config.operationBusy)
                self.assertLess(call_elapsed, 0.1)
                wait_for_idle(config)

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
            (tmp_path / "model_profiles.json").write_text(
                (ROOT / "model_profiles.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            config = codex_config.CodexConfig()
            wait_for_idle(config)
            config.setKey("new-key")
            wait_for_idle(config)

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

    def test_corrupt_auth_does_not_hide_valid_config(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'name = "relay"\nbase_url = "https://gateway.example.com/v1"\n'
                'wire_api = "responses"\n',
                encoding="utf-8",
            )
            (codex_home / "auth.json").write_text("{broken", encoding="utf-8")
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.reload()
            wait_for_idle(config)

            self.assertEqual(config.baseUrl, "https://gateway.example.com/v1")
            self.assertFalse(config.hasKey)
            self.assertTrue(
                any(
                    title == "认证读取失败" and "auth.json" in message
                    for _, title, message in notices
                )
            )

            config.fetchModels("https://gateway.example.com/v1", "")
            wait_for_idle(config, "modelsLoading")
            self.assertFalse(config.modelsLoading)
            self.assertTrue(any(title == "获取失败" for _, title, _ in notices))

    def test_atomic_write_failure_preserves_existing_config_and_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            auth_path = codex_home / "auth.json"
            old_config = 'model_provider = "old"\n'
            old_auth = '{"OPENAI_API_KEY": "old-key"}\n'
            config_path.write_text(old_config, encoding="utf-8")
            auth_path.write_text(old_auth, encoding="utf-8")
            store = CodexConfigStore(str(codex_home))

            with patch(
                "backend.codex_config_store.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    store.apply_config(self.store_values())
                with self.assertRaisesRegex(OSError, "replace failed"):
                    store.set_key("new-key")

            self.assertEqual(config_path.read_text(encoding="utf-8"), old_config)
            self.assertEqual(auth_path.read_text(encoding="utf-8"), old_auth)
            self.assertEqual(list(codex_home.glob(".*.tmp")), [])

    def test_invalid_provider_is_rejected_without_touching_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            original = 'model_provider = "relay"\n'
            config_path.write_text(original, encoding="utf-8")
            store = CodexConfigStore(str(codex_home))

            with self.assertRaisesRegex(ValueError, "provider"):
                store.apply_config(self.store_values('relay"]\nmalicious = "yes'))

            self.assertEqual(config_path.read_text(encoding="utf-8"), original)

    def test_model_profiles_match_gpt56_and_preserve_other_models(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            expected_values = ["low", "medium", "high", "xhigh"]
            expected_text = ["轻度", "中", "高", "极高"]
            for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
                options = config.reasoningOptionsForModel(model)
                self.assertEqual([item["value"] for item in options], expected_values)
                self.assertEqual([item["text"] for item in options], expected_text)
                self.assertEqual(
                    config.highestReasoningEffortForModel(model), "xhigh"
                )
                self.assertEqual(
                    config.contextPresetForModel(model),
                    {
                        "menuText": "稳定上下文",
                        "contextWindow": 258400,
                        "autoCompactLimit": 245000,
                        "toolOutputLimit": 6000,
                        "maxContextWindow": 258400,
                        "maxAutoCompactLimit": 245000,
                    },
                )

            gpt55_options = config.reasoningOptionsForModel("gpt-5.5")
            self.assertEqual(
                [item["value"] for item in gpt55_options],
                ["", "low", "medium", "high", "xhigh"],
            )
            self.assertEqual(
                config.highestReasoningEffortForModel("gpt-5.5"), "xhigh"
            )
            self.assertEqual(
                config.contextPresetForModel("gpt-5.5"),
                {
                    "menuText": "稳定上下文",
                    "contextWindow": 258400,
                    "autoCompactLimit": 245000,
                    "toolOutputLimit": 6000,
                    "maxContextWindow": 258400,
                    "maxAutoCompactLimit": 245000,
                },
            )

            other_options = config.reasoningOptionsForModel("custom-model")
            self.assertEqual(
                [item["value"] for item in other_options],
                ["", "low", "medium", "high", "xhigh"],
            )
            self.assertEqual(
                config.highestReasoningEffortForModel("custom-model"), "xhigh"
            )
            self.assertEqual(config.contextPresetForModel("custom-model"), {})
            self.assertEqual(
                config.stableContextPreset(),
                {
                    "menuText": "稳定上下文",
                    "contextWindow": 258400,
                    "autoCompactLimit": 245000,
                    "toolOutputLimit": 6000,
                    "maxContextWindow": 258400,
                    "maxAutoCompactLimit": 245000,
                },
            )

    def test_apply_real_gpt56_config_sample(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            config_path.write_text(
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'name = "relay"\nbase_url = "https://api.9li.life/v1"\n'
                'wire_api = "responses"\n',
                encoding="utf-8",
            )
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )
            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life/v1",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                    "reasoningEffort": "max",
                }
            )
            self.assertEqual(
                notices[-1],
                (2, "参数无效", "gpt-5.6-sol 不支持思考等级 max"),
            )
            with config_path.open("rb") as handle:
                rejected = tomllib.load(handle)
            self.assertNotIn("model", rejected)
            self.assertNotIn("model_reasoning_effort", rejected)

            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life/v1",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                    "reasoningEffort": "xhigh",
                    "modelContextWindow": "372000",
                    "modelAutoCompactTokenLimit": "353000",
                    "toolOutputTokenLimit": "6000",
                }
            )
            wait_for_idle(config)

            with config_path.open("rb") as handle:
                saved = tomllib.load(handle)
            self.assertEqual(saved["model"], "gpt-5.6-sol")
            self.assertEqual(saved["model_reasoning_effort"], "xhigh")
            self.assertEqual(saved["model_context_window"], 258400)
            self.assertEqual(saved["model_auto_compact_token_limit"], 245000)
            self.assertEqual(saved["tool_output_token_limit"], 6000)

    def test_model_fetch_notification_does_not_embed_model_list(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex_home = tmp_path / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            model_ids = [
                "codex-auto-review",
                "gpt-5.4",
                "gpt-5.4-mini",
                "gpt-5.5",
                "gpt-5.5-openai-compact",
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "model-9",
                "model-10",
                "model-11",
            ]

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return json.dumps(
                        {
                            "data": [
                                {
                                    "id": model_id,
                                    **(
                                        {
                                            "supported_reasoning_levels": [
                                                {"effort": "low"},
                                                {"effort": "medium"},
                                                {"effort": "high"},
                                                {"effort": "xhigh"},
                                                {"effort": "max"},
                                                {"effort": "ultra"},
                                            ]
                                        }
                                        if model_id == "gpt-5.6-sol"
                                        else {}
                                    ),
                                }
                                for model_id in model_ids
                            ]
                        }
                    ).encode("utf-8")

            with patch("urllib.request.urlopen", return_value=Response()):
                config.fetchModels("https://example.test/v1", "")
                wait_for_idle(config, "modelsLoading")

            self.assertEqual(config.availableModels, model_ids)
            self.assertEqual(
                notices[-1],
                (1, "获取到 11 个模型", "思考等级已从远端同步"),
            )
            self.assertEqual(
                config.reasoningOptionsForModel("gpt-5.6-sol"),
                [
                    {"value": "low", "text": "轻度"},
                    {"value": "medium", "text": "中"},
                    {"value": "high", "text": "高"},
                    {"value": "xhigh", "text": "极高"},
                ],
            )

    def test_key_save_and_immediate_model_fetch_uses_new_key(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            (codex_home / "auth.json").write_text(
                json.dumps({"OPENAI_API_KEY": "old-key"}),
                encoding="utf-8",
            )
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            save_started = threading.Event()
            release_save = threading.Event()
            authorization_used = []
            original_set_key = config._store.set_key

            def slow_set_key(key):
                save_started.set()
                release_save.wait(1)
                return original_set_key(key)

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return (
                        b'{"data":[{"id":"gpt-5.6-sol",'
                        b'"supported_reasoning_levels":[{"effort":"high"}]}]}'
                    )

            def urlopen(request, timeout):
                authorization_used.append(request.get_header("Authorization"))
                return Response()

            with (
                patch.object(config._store, "set_key", side_effect=slow_set_key),
                patch("urllib.request.urlopen", side_effect=urlopen),
            ):
                config.setKey("new-key")
                self.assertTrue(save_started.wait(1))
                config.fetchModels("https://gateway.example.com/v1", "")
                release_save.set()
                wait_until(
                    lambda: not config.operationBusy and not config.modelsLoading,
                    timeout=2,
                )

            self.assertEqual(authorization_used, ["Bearer new-key"])

    def test_catalog_refresh_does_not_block_user_model_request(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            catalog_started = threading.Event()
            release_catalog = threading.Event()
            request_started = threading.Event()

            def slow_catalog():
                catalog_started.set()
                release_catalog.wait(1)
                return []

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return (
                        b'{"data":[{"id":"gpt-5.6-sol",'
                        b'"supported_reasoning_levels":[{"effort":"high"}]}]}'
                    )

            def urlopen(request, timeout):
                request_started.set()
                return Response()

            with (
                patch.object(
                    codex_config,
                    "fetch_codex_model_catalog",
                    side_effect=slow_catalog,
                ),
                patch("urllib.request.urlopen", side_effect=urlopen),
            ):
                config.refreshReasoningProfiles()
                self.assertTrue(catalog_started.wait(1))
                config.fetchModels("https://gateway.example.com/v1", "new-key")
                self.assertTrue(
                    request_started.wait(0.5),
                    "用户模型请求被目录刷新队列阻塞",
                )
                release_catalog.set()
                wait_until(
                    lambda: not config.modelsLoading
                    and not config._reasoning_refresh_pending,
                    timeout=2,
                )

    def test_real_relay_host_gets_v1_for_config_and_model_fetch(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                }
            )
            wait_for_idle(config)
            with (codex_home / "config.toml").open("rb") as handle:
                saved = tomllib.load(handle)
            self.assertEqual(
                saved["model_providers"]["relay"]["base_url"],
                "https://api.9li.life/v1",
            )

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return b'{"data":[{"id":"gpt-5.6-sol"}]}'

            with (
                patch("urllib.request.urlopen", return_value=Response()) as mocked,
                patch(
                    "backend.codex_config.fetch_codex_model_catalog",
                    return_value=[],
                ),
            ):
                config.fetchModels("https://api.9li.life", "")
                wait_for_idle(config, "modelsLoading")
            self.assertEqual(
                mocked.call_args.args[0].full_url,
                "https://api.9li.life/v1/models",
            )

    def test_slow_config_write_does_not_block_gui_thread(self):
        codex_config = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)
            timer_fired = []

            def slow_apply(values):
                time.sleep(0.2)
                snapshot = config._store.read_snapshot()
                snapshot["baseUrl"] = values["baseUrl"]
                return snapshot

            with patch.object(config._store, "apply_config", side_effect=slow_apply):
                QTimer.singleShot(10, lambda: timer_fired.append(True))
                started = time.perf_counter()
                config.applyConfig(
                    {
                        "baseUrl": "https://gateway.example.com",
                        "provider": "relay",
                        "wireApi": "responses",
                        "model": "gpt-5.6-sol",
                    }
                )
                call_elapsed = time.perf_counter() - started
                wait_until(lambda: bool(timer_fired), timeout=0.15)
                self.assertTrue(config.operationBusy)
                self.assertLess(call_elapsed, 0.1)
                wait_for_idle(config)


if __name__ == "__main__":
    unittest.main()
