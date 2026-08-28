import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from PySide6.QtCore import QTimer

from tests.qt_test_utils import wait_for_idle, wait_until


ROOT = Path(__file__).resolve().parents[1]


class ClaudeDesktopConfigTests(unittest.TestCase):
    def load_module(self):
        import importlib
        import sys

        sys.path.insert(0, str(ROOT))
        sys.modules.pop("backend.claude_desktop_config", None)
        return importlib.import_module("backend.claude_desktop_config")

    def load_install_module(self):
        import importlib
        import sys

        sys.path.insert(0, str(ROOT))
        sys.modules.pop("backend.claude_install_sources", None)
        return importlib.import_module("backend.claude_install_sources")

    def make_config(self, module, root: Path):
        primary = root / "Claude"
        third_party = root / "Claude-3p"
        executable = root / "AnthropicClaude" / "claude.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        patches = mock.patch.dict(
            os.environ,
            {
                "CONFIGPILOT_CLAUDE_PRIMARY_DATA_DIR": str(primary),
                "CONFIGPILOT_CLAUDE_DATA_DIR": str(third_party),
                "CONFIGPILOT_CLAUDE_EXECUTABLE": str(executable),
            },
        )
        patches.start()
        self.addCleanup(patches.stop)
        config = module.ClaudeDesktopConfig()
        wait_for_idle(config)
        return config, primary, third_party

    @staticmethod
    def write_json(path: Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_reload_reads_active_profile_without_exposing_api_key(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            third_party = root / "Claude-3p"
            self.write_json(
                third_party / "developer_settings.json", {"allowDevTools": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p", "preferences": {"sidebarMode": "default"}},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": profile_id,
                    "entries": [{"id": profile_id, "name": "ConfigPilot"}],
                },
            )
            self.write_json(
                third_party / "configLibrary" / f"{profile_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://gateway.example.com",
                    "inferenceGatewayApiKey": "secret-value",
                    "inferenceGatewayAuthScheme": "x-api-key",
                    "inferenceModels": ["model-a", {"name": "model-b"}],
                    "inferenceCustomHeaders": {"X-Tenant": "demo"},
                },
            )

            config, _, _ = self.make_config(module, root)

            self.assertTrue(config.installed)
            self.assertTrue(config.developerModeEnabled)
            self.assertTrue(config.thirdPartyEnabled)
            self.assertEqual(config.endpoint, "https://gateway.example.com")
            self.assertEqual(config.authScheme, "x-api-key")
            self.assertEqual(config.modelsText, "model-a\nmodel-b")
            self.assertEqual(
                json.loads(config.modelsJson),
                ["model-a", {"name": "model-b"}],
            )
            self.assertEqual(config.modelDiscoveryState, "auto")
            self.assertEqual(config.modelPrefer1mContextState, "auto")
            self.assertTrue(config.hasApiKey)
            self.assertEqual(config.headerCount, 1)
            self.assertEqual(config.profileName, "ConfigPilot")
            self.assertNotIn("secret-value", vars(config).values())

    def test_reload_ignores_unrelated_active_profile(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            configpilot_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            other_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": other_id,
                    "entries": [
                        {"id": configpilot_id, "name": "ConfigPilot"},
                        {"id": other_id, "name": "CC Switch"},
                    ],
                },
            )
            self.write_json(
                third_party / "configLibrary" / f"{configpilot_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://configpilot.example.com",
                    "inferenceModels": [
                        {
                            "name": "claude-sonnet-5",
                            "labelOverride": "Claude Sonnet 5",
                            "supports1m": True,
                            "prefer1m": True,
                        }
                    ],
                },
            )
            self.write_json(
                third_party / "configLibrary" / f"{other_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                    "inferenceGatewayApiKey": "other-secret",
                },
            )

            config, _, _ = self.make_config(module, root)

            self.assertEqual(config.profileName, "ConfigPilot")
            self.assertEqual(config.endpoint, "https://configpilot.example.com")
            self.assertEqual(config.modelsText, "claude-sonnet-5")
            self.assertFalse(config.thirdPartyEnabled)

    def test_reload_exposes_unrelated_active_profile_for_import(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            active_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": active_id,
                    "entries": [{"id": active_id, "name": "CC Switch"}],
                },
            )
            self.write_json(
                third_party / "configLibrary" / f"{active_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                },
            )

            config, _, _ = self.make_config(module, root)

            self.assertFalse(config.configPilotProfileExists)
            self.assertEqual(config.activeProfileName, "CC Switch")
            self.assertTrue(config.canImportActiveProfile)
            self.assertEqual(config.profileName, "")
            self.assertEqual(config.endpoint, "https://cc-switch.example.com")
            self.assertEqual(config.modelsText, "")

    def test_apply_updates_configpilot_without_replacing_unrelated_profile(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            other_id = "00000000-0000-4000-8000-000000157210"
            configpilot_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": other_id,
                    "entries": [
                        {"id": configpilot_id, "name": "ConfigPilot"},
                        {"id": other_id, "name": "CC Switch"},
                    ],
                },
            )
            original_other = {
                "inferenceProvider": "gateway",
                "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                "inferenceGatewayApiKey": "other-secret",
            }
            self.write_json(
                third_party / "configLibrary" / f"{other_id}.json",
                original_other,
            )
            self.write_json(
                third_party / "configLibrary" / f"{configpilot_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://old.example.com",
                },
            )

            config, _, _ = self.make_config(module, root)
            config.applyConfig(
                {
                    "endpoint": "https://new.example.com",
                    "authScheme": "bearer",
                    "modelsText": "claude-sonnet-5",
                }
            )
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(meta["appliedId"], configpilot_id)
            self.assertEqual(len(meta["entries"]), 2)
            self.assertEqual(
                json.loads(
                    (third_party / "configLibrary" / f"{other_id}.json").read_text(
                        encoding="utf-8"
                    )
                ),
                original_other,
            )
            profile = json.loads(
                (third_party / "configLibrary" / f"{configpilot_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(profile["inferenceGatewayBaseUrl"], "https://new.example.com")
            self.assertEqual(profile["inferenceModels"], ["claude-sonnet-5"])

    def test_apply_writes_structured_models_and_context_states(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, third_party = self.make_config(module, Path(tmp))
            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsJson": json.dumps(
                        [
                            {
                                "name": "claude-sonnet-5",
                                "labelOverride": "Claude Sonnet 5",
                                "supports1m": True,
                                "prefer1m": True,
                                "anthropicFamilyTier": "sonnet",
                                "isFamilyDefault": True,
                                "futureCapability": "preserve-me",
                            },
                            "claude-haiku-4-5-20251001",
                        ]
                    ),
                    "modelDiscoveryState": "enabled",
                    "modelPrefer1mContextState": "disabled",
                }
            )
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            profile = json.loads(
                (
                    third_party
                    / "configLibrary"
                    / f"{meta['appliedId']}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                profile["inferenceModels"],
                [
                    {
                        "name": "claude-sonnet-5",
                        "labelOverride": "Claude Sonnet 5",
                        "supports1m": True,
                        "prefer1m": True,
                        "anthropicFamilyTier": "sonnet",
                        "isFamilyDefault": True,
                        "futureCapability": "preserve-me",
                    },
                    "claude-haiku-4-5-20251001",
                ],
            )
            self.assertTrue(profile["modelDiscoveryEnabled"])
            self.assertFalse(profile["modelPrefer1mContext"])
            self.assertEqual(config.modelsText, "claude-sonnet-5\nclaude-haiku-4-5-20251001")
            self.assertEqual(config.modelDiscoveryState, "enabled")
            self.assertEqual(config.modelPrefer1mContextState, "disabled")

    def test_disabling_model_discovery_requires_fixed_models(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            config, _, third_party = self.make_config(module, Path(tmp))
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )
            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsJson": "[]",
                    "modelDiscoveryState": "disabled",
                }
            )
            wait_for_idle(config)

            self.assertFalse((third_party / "configLibrary").exists())
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("固定模型", notices[-1][2])

    def test_apply_creates_configpilot_without_overwriting_cc_switch(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            cc_switch_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": cc_switch_id,
                    "entries": [{"id": cc_switch_id, "name": "CC Switch"}],
                },
            )
            cc_switch_profile = {
                "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                "inferenceGatewayApiKey": "cc-switch-secret",
                "modelDiscoveryEnabled": True,
                "modelPrefer1mContext": True,
                "inferenceModels": [
                    {
                        "name": "claude-sonnet-5",
                        "labelOverride": "Claude Sonnet 5",
                        "supports1m": True,
                        "prefer1m": True,
                    }
                ],
                "inferenceProvider": "gateway",
                "inferenceCredentialKind": "static",
            }
            cc_switch_path = (
                third_party / "configLibrary" / f"{cc_switch_id}.json"
            )
            self.write_json(cc_switch_path, cc_switch_profile)
            original_cc_switch = cc_switch_path.read_text(encoding="utf-8")

            config, _, _ = self.make_config(module, root)
            config.applyConfig(
                {
                    "endpoint": "https://configpilot.example.com",
                    "authScheme": "bearer",
                    "modelsText": "claude-opus-5",
                }
            )
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(meta["entries"]), 2)
            configpilot_entries = [
                entry for entry in meta["entries"] if entry["name"] == "ConfigPilot"
            ]
            self.assertEqual(len(configpilot_entries), 1)
            self.assertEqual(meta["appliedId"], configpilot_entries[0]["id"])
            self.assertNotEqual(meta["appliedId"], cc_switch_id)
            self.assertEqual(cc_switch_path.read_text(encoding="utf-8"), original_cc_switch)
            self.assertFalse(cc_switch_path.with_name(cc_switch_path.name + ".bak").exists())
            configpilot_path = third_party / "configLibrary" / f"{meta['appliedId']}.json"
            configpilot_profile = json.loads(configpilot_path.read_text(encoding="utf-8"))
            self.assertEqual(
                configpilot_profile["inferenceGatewayApiKey"],
                "cc-switch-secret",
            )
            self.assertTrue(configpilot_profile["modelDiscoveryEnabled"])
            self.assertTrue(configpilot_profile["modelPrefer1mContext"])

    def test_clone_active_profile_creates_configpilot_and_preserves_source(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            cc_switch_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p", "preferences": {"sidebarMode": "epitaxy"}},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": cc_switch_id,
                    "entries": [{"id": cc_switch_id, "name": "CC Switch"}],
                },
            )
            source_profile = {
                "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                "inferenceGatewayApiKey": "cc-switch-secret",
                "modelDiscoveryEnabled": True,
                "modelPrefer1mContext": True,
                "inferenceModels": [
                    {
                        "name": "claude-sonnet-5",
                        "labelOverride": "Claude Sonnet 5",
                        "supports1m": True,
                        "prefer1m": True,
                    }
                ],
                "inferenceProvider": "gateway",
                "inferenceCredentialKind": "static",
            }
            source_path = third_party / "configLibrary" / f"{cc_switch_id}.json"
            self.write_json(source_path, source_profile)
            original_source = source_path.read_text(encoding="utf-8")

            config, _, _ = self.make_config(module, root)
            config.cloneActiveProfileToConfigPilot()
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            configpilot_entries = [
                entry for entry in meta["entries"] if entry["name"] == "ConfigPilot"
            ]
            self.assertEqual(len(configpilot_entries), 1)
            configpilot_id = configpilot_entries[0]["id"]
            self.assertNotEqual(configpilot_id, cc_switch_id)
            self.assertEqual(meta["appliedId"], configpilot_id)
            self.assertEqual(source_path.read_text(encoding="utf-8"), original_source)
            self.assertFalse(source_path.with_name(source_path.name + ".bak").exists())

            cloned_path = third_party / "configLibrary" / f"{configpilot_id}.json"
            self.assertEqual(json.loads(cloned_path.read_text(encoding="utf-8")), source_profile)
            self.assertEqual(config.profileName, "ConfigPilot")
            self.assertEqual(config.activeProfileName, "ConfigPilot")
            self.assertFalse(config.canImportActiveProfile)
            self.assertEqual(config.endpoint, "https://cc-switch.example.com")
            self.assertEqual(config.modelsText, "claude-sonnet-5")

    def test_profile_id_collision_with_cc_switch_is_rejected(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            shared_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": shared_id,
                    "entries": [
                        {"id": shared_id, "name": "ConfigPilot"},
                        {"id": shared_id, "name": "CC Switch"},
                    ],
                },
            )
            profile_path = third_party / "configLibrary" / f"{shared_id}.json"
            self.write_json(
                profile_path,
                {
                    "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                    "inferenceGatewayApiKey": "cc-switch-secret",
                },
            )
            original_profile = profile_path.read_text(encoding="utf-8")
            config, _, _ = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )
            config.applyConfig(
                {
                    "endpoint": "https://configpilot.example.com",
                    "authScheme": "bearer",
                    "modelsText": "claude-opus-5",
                }
            )
            wait_for_idle(config)

            self.assertEqual(profile_path.read_text(encoding="utf-8"), original_profile)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("CC Switch", notices[-1][2])

    def test_new_configpilot_id_collision_is_rejected(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            cc_switch_id = "00000000-0000-4000-8000-000000157210"
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p"},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": cc_switch_id,
                    "entries": [{"id": cc_switch_id, "name": "CC Switch"}],
                },
            )
            cc_switch_path = (
                third_party / "configLibrary" / f"{cc_switch_id}.json"
            )
            self.write_json(
                cc_switch_path,
                {
                    "inferenceGatewayBaseUrl": "https://cc-switch.example.com",
                    "inferenceGatewayApiKey": "cc-switch-secret",
                },
            )
            original_meta = (third_party / "configLibrary" / "_meta.json").read_text(
                encoding="utf-8"
            )
            original_profile = cc_switch_path.read_text(encoding="utf-8")

            config, _, _ = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )
            with mock.patch.object(module.uuid, "uuid4", return_value=mock.Mock(__str__=lambda _: cc_switch_id)):
                config.applyConfig(
                    {
                        "endpoint": "https://configpilot.example.com",
                        "authScheme": "bearer",
                        "modelsText": "claude-opus-5",
                    }
                )
                wait_for_idle(config)

            self.assertEqual(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                ),
                original_meta,
            )
            self.assertEqual(cc_switch_path.read_text(encoding="utf-8"), original_profile)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("冲突", notices[-1][2])

    def test_slow_install_detection_does_not_block_gui_thread(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _ = self.make_config(module, Path(tmp))
            timer_fired = []

            def slow_detection(target):
                time.sleep(0.2)
                return True

            with mock.patch.object(
                module,
                "claude_desktop_installed",
                side_effect=slow_detection,
            ):
                QTimer.singleShot(10, lambda: timer_fired.append(True))
                started = time.perf_counter()
                config.reload()
                call_elapsed = time.perf_counter() - started
                wait_until(lambda: bool(timer_fired), timeout=0.15)
                self.assertTrue(config.operationBusy)
                self.assertLess(call_elapsed, 0.1)
                wait_for_idle(config)

    def test_open_config_directory_shell_dispatch_runs_off_main_thread(self):
        module = self.load_module()
        main_thread = threading.get_ident()
        opener_calls = []
        timer_fired = []

        with tempfile.TemporaryDirectory() as tmp:
            config, _, third_party = self.make_config(module, Path(tmp))

            def slow_opener(target):
                opener_calls.append((Path(target), threading.get_ident()))
                time.sleep(0.2)
                return True

            with mock.patch.object(
                module,
                "open_external_target",
                side_effect=slow_opener,
            ):
                QTimer.singleShot(10, lambda: timer_fired.append(True))
                before = time.perf_counter()
                config.openConfigDirectory()
                elapsed = time.perf_counter() - before
                wait_until(lambda: bool(timer_fired), timeout=0.15)
                wait_for_idle(config)

        self.assertLess(elapsed, 0.1)
        self.assertEqual(opener_calls[0][0], third_party)
        self.assertNotEqual(opener_calls[0][1], main_thread)

    def test_apply_creates_profile_enables_developer_mode_and_preserves_settings(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, primary, third_party = self.make_config(module, root)
            self.write_json(
                primary / "developer_settings.json", {"useMacMenuBarHelper": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"preferences": {"sidebarMode": "default"}},
            )
            config.reload()
            wait_for_idle(config)

            notices = []
            config.notify.connect(lambda level, title, message: notices.append((level, title, message)))
            config.applyConfig(
                {
                    "endpoint": "https://api.9li.life",
                    "authScheme": "bearer",
                    "modelsText": "model-a\nmodel-b\nmodel-a",
                    "apiKey": "new-secret",
                    "headersText": '{"X-Tenant": "demo"}',
                }
            )
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(meta["entries"]), 1)
            self.assertEqual(meta["entries"][0]["name"], "ConfigPilot")
            profile_path = (
                third_party / "configLibrary" / f"{meta['appliedId']}.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["inferenceProvider"], "gateway")
            self.assertEqual(profile["inferenceCredentialKind"], "static")
            self.assertEqual(
                profile["inferenceGatewayBaseUrl"], "https://api.9li.life"
            )
            self.assertEqual(profile["inferenceGatewayAuthScheme"], "bearer")
            self.assertEqual(profile["inferenceGatewayApiKey"], "new-secret")
            self.assertEqual(profile["inferenceModels"], ["model-a", "model-b"])
            self.assertEqual(profile["inferenceCustomHeaders"], {"X-Tenant": "demo"})

            primary_settings = json.loads(
                (primary / "developer_settings.json").read_text(encoding="utf-8")
            )
            third_party_settings = json.loads(
                (third_party / "developer_settings.json").read_text(encoding="utf-8")
            )
            desktop_config = json.loads(
                (third_party / "claude_desktop_config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(primary_settings["allowDevTools"])
            self.assertTrue(primary_settings["useMacMenuBarHelper"])
            self.assertTrue(third_party_settings["allowDevTools"])
            self.assertEqual(desktop_config["deploymentMode"], "3p")
            self.assertEqual(
                desktop_config["preferences"], {"sidebarMode": "default"}
            )
            self.assertTrue(
                (third_party / "claude_desktop_config.json.bak").is_file()
            )
            self.assertEqual(notices[-1][0], 1)

    def test_sensitive_fields_are_preserved_until_explicitly_cleared(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            third_party = root / "Claude-3p"
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": profile_id,
                    "entries": [{"id": profile_id, "name": "ConfigPilot"}],
                },
            )
            profile_path = third_party / "configLibrary" / f"{profile_id}.json"
            self.write_json(
                profile_path,
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://old.example.com",
                    "inferenceGatewayApiKey": "old-secret",
                    "inferenceCustomHeaders": {"X-Secret": "keep-me"},
                },
            )
            config, _, _ = self.make_config(module, root)

            config.applyConfig(
                {
                    "endpoint": "https://new.example.com",
                    "authScheme": "bearer",
                    "modelsText": "",
                    "apiKey": "",
                    "headersText": "",
                }
            )
            wait_for_idle(config)
            preserved = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(preserved["inferenceGatewayApiKey"], "old-secret")
            self.assertEqual(
                preserved["inferenceCustomHeaders"], {"X-Secret": "keep-me"}
            )

            config.applyConfig(
                {
                    "endpoint": "https://new.example.com",
                    "authScheme": "x-api-key",
                    "modelsText": "",
                    "clearApiKey": True,
                    "clearHeaders": True,
                }
            )
            wait_for_idle(config)
            cleared = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertNotIn("inferenceGatewayApiKey", cleared)
            self.assertNotIn("inferenceCustomHeaders", cleared)
            self.assertNotIn("inferenceGatewayHeaders", cleared)

    def test_individual_mode_toggles_preserve_gateway_profile_and_settings(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, primary, third_party = self.make_config(module, root)
            self.write_json(
                primary / "developer_settings.json", {"useMacMenuBarHelper": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"preferences": {"sidebarMode": "default"}},
            )
            config.reload()
            wait_for_idle(config)
            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsText": "model-a",
                    "apiKey": "keep-secret",
                }
            )
            wait_for_idle(config)

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            profile_path = (
                third_party / "configLibrary" / f"{meta['appliedId']}.json"
            )
            original_profile = profile_path.read_text(encoding="utf-8")

            config.setDeveloperModeEnabled(False)
            config.setThirdPartyEnabled(False)
            wait_for_idle(config)

            primary_settings = json.loads(
                (primary / "developer_settings.json").read_text(encoding="utf-8")
            )
            third_party_settings = json.loads(
                (third_party / "developer_settings.json").read_text(
                    encoding="utf-8"
                )
            )
            desktop_config = json.loads(
                (third_party / "claude_desktop_config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(primary_settings["allowDevTools"])
            self.assertTrue(primary_settings["useMacMenuBarHelper"])
            self.assertFalse(third_party_settings["allowDevTools"])
            self.assertEqual(desktop_config["deploymentMode"], "1p")
            self.assertEqual(
                desktop_config["preferences"], {"sidebarMode": "default"}
            )
            self.assertEqual(profile_path.read_text(encoding="utf-8"), original_profile)
            self.assertFalse(config.developerModeEnabled)
            self.assertFalse(config.thirdPartyEnabled)

            config.setDeveloperModeEnabled(True)
            config.setThirdPartyEnabled(True)
            wait_for_idle(config)

            self.assertTrue(config.developerModeEnabled)
            self.assertTrue(config.thirdPartyEnabled)
            self.assertEqual(profile_path.read_text(encoding="utf-8"), original_profile)

    def test_gateway_toggle_requires_a_saved_gateway_profile(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, third_party = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.setThirdPartyEnabled(True)
            wait_for_idle(config)

            self.assertFalse(
                (third_party / "claude_desktop_config.json").exists()
            )
            self.assertFalse(config.thirdPartyEnabled)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("尚未保存 Gateway 配置", notices[-1][2])

    def test_official_install_sources_are_selected_for_each_platform(self):
        install_module = self.load_install_module()
        sources = json.loads(
            (ROOT / "resources" / "claude_install_sources.json").read_text(
                encoding="utf-8"
            )
        )
        cases = (
            ("win32", "AMD64", "windows-x64", "windows-exe"),
            ("win32", "ARM64", "windows-arm64", "windows-exe"),
            ("darwin", "arm64", "macos-universal", "macos-dmg"),
            ("linux", "x86_64", "linux", "linux-deb"),
        )
        for platform_name, machine, source_key, expected_kind in cases:
            with self.subTest(platform=platform_name, machine=machine), mock.patch.object(
                install_module.sys, "platform", platform_name
            ), mock.patch.object(
                install_module.platform, "machine", return_value=machine
            ):
                spec = install_module.official_install_spec("claude-desktop")
                self.assertEqual(spec.kind, expected_kind)
                source = sources["claudeDesktop"][source_key]
                if expected_kind == "linux-deb":
                    self.assertEqual(spec.help_url, source["helpUrl"])
                    self.assertIn("binary-amd64/Packages", spec.packages_url)
                else:
                    self.assertEqual(spec.url, source["url"])

        for platform_name, expected_key, expected_kind in (
            ("win32", "windows", "powershell-script"),
            ("linux", "unix", "shell-script"),
            ("darwin", "unix", "shell-script"),
        ):
            with self.subTest(code_platform=platform_name), mock.patch.object(
                install_module.sys, "platform", platform_name
            ):
                spec = install_module.official_install_spec("claude-code")
            self.assertEqual(spec.kind, expected_kind)
            self.assertEqual(spec.url, sources["claudeCode"][expected_key]["url"])

        windows_urls = [
            sources["claudeDesktop"][key]["url"]
            for key in ("windows-x64", "windows-arm64")
        ]
        self.assertTrue(all("microsoft" not in url.lower() for url in windows_urls))
        self.assertTrue(all("/api/desktop/win32/" in url for url in windows_urls))

    def test_linux_install_detection_uses_official_apt_package(self):
        module = self.load_install_module()
        installed = mock.Mock(
            returncode=0,
            stdout="install ok installed\n",
        )
        missing = mock.Mock(returncode=1, stdout="")

        with mock.patch.object(module.sys, "platform", "linux"), mock.patch.object(
            module.subprocess, "run", return_value=installed
        ) as run:
            self.assertTrue(module.claude_desktop_installed(None))
        run.assert_called_once_with(
            ["dpkg-query", "-W", "-f=${Status}", "claude-desktop"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )

        with mock.patch.object(module.sys, "platform", "linux"), mock.patch.object(
            module.subprocess, "run", return_value=missing
        ):
            self.assertFalse(module.claude_desktop_installed(None))

    def test_unknown_install_product_does_not_start_download(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, _ = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.installProduct("unknown")
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("未知的 Claude 安装项", notices[-1][2])

    def test_invalid_input_does_not_create_configuration(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, third_party = self.make_config(module, root)
            notices = []
            config.notify.connect(lambda level, title, message: notices.append((level, title, message)))

            config.applyConfig(
                {
                    "endpoint": "not-a-url",
                    "authScheme": "auto",
                    "modelsText": "model-a",
                    "headersText": "[]",
                }
            )
            wait_for_idle(config)

            self.assertFalse((third_party / "configLibrary").exists())
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("Gateway endpoint", notices[-1][2])

    def test_invalid_existing_meta_is_not_overwritten(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            meta_path = third_party / "configLibrary" / "_meta.json"
            self.write_json(
                meta_path,
                {"appliedId": "broken", "entries": [{"id": "broken"}]},
            )
            original = meta_path.read_text(encoding="utf-8")
            config, _, _ = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsText": "model-a",
                }
            )
            wait_for_idle(config)

            self.assertEqual(meta_path.read_text(encoding="utf-8"), original)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("无效配置条目", notices[-1][2])


if __name__ == "__main__":
    unittest.main()
