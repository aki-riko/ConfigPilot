import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.codex_model_catalog import fetch_codex_model_catalog, model_items
from backend.model_profiles import ModelProfiles


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CodexModelCatalogTests(unittest.TestCase):
    def test_model_items_accepts_verified_codex_and_provider_shapes(self):
        models = [{"slug": "gpt-5.6-sol"}]
        self.assertEqual(model_items({"models": models}), models)
        self.assertEqual(model_items({"data": models}), models)

    @patch("backend.codex_model_catalog.subprocess.run")
    @patch("backend.codex_model_catalog.shutil.which", return_value="codex")
    def test_fetch_uses_remote_refreshing_codex_catalog(self, _, mocked_run):
        payload = {
            "models": [
                {
                    "slug": "gpt-5.6-sol",
                    "supported_reasoning_levels": [
                        {"effort": "low"},
                        {"effort": "medium"},
                        {"effort": "high"},
                        {"effort": "xhigh"},
                    ],
                }
            ]
        }
        mocked_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

        self.assertEqual(fetch_codex_model_catalog(), payload["models"])
        self.assertEqual(
            mocked_run.call_args.args[0], ["codex", "debug", "models"]
        )

    def test_remote_levels_override_static_fallback_by_exact_model(self):
        profiles = ModelProfiles.from_file("model_profiles.json")
        updated = profiles.update_reasoning_from_models(
            [
                {
                    "slug": "gpt-5.6-sol",
                    "supported_reasoning_levels": [
                        {"effort": "medium"},
                        {"effort": "high"},
                    ],
                }
            ]
        )

        self.assertEqual(updated, 1)
        self.assertEqual(
            profiles.reasoning_options("gpt-5.6-sol"),
            [
                {"value": "medium", "text": "中"},
                {"value": "high", "text": "高"},
            ],
        )
        self.assertEqual(profiles.highest_reasoning_effort("gpt-5.6-sol"), "high")
        self.assertFalse(profiles.supports_reasoning_effort("gpt-5.6-sol", "xhigh"))

    def test_remote_catalog_includes_gpt56_max_but_excludes_ultra(self):
        profiles = ModelProfiles.from_file("model_profiles.json")
        payload = json.loads(
            (FIXTURES / "codex_gpt56_sol_catalog.json").read_text(encoding="utf-8")
        )
        updated = profiles.update_reasoning_from_models(payload["models"])

        self.assertEqual(updated, 1)
        self.assertEqual(
            [
                option["value"]
                for option in profiles.reasoning_options("gpt-5.6-sol")
            ],
            ["low", "medium", "high", "xhigh", "max"],
        )
        self.assertTrue(profiles.supports_reasoning_effort("gpt-5.6-sol", "max"))
        self.assertFalse(profiles.supports_reasoning_effort("gpt-5.6-sol", "ultra"))

    def test_remote_max_remains_filtered_for_models_without_static_support(self):
        profiles = ModelProfiles.from_file("model_profiles.json")
        updated = profiles.update_reasoning_from_models(
            [
                {
                    "slug": "gpt-5.5",
                    "supported_reasoning_levels": [
                        {"effort": "high"},
                        {"effort": "max"},
                    ],
                }
            ]
        )

        self.assertEqual(updated, 1)
        self.assertEqual(
            [option["value"] for option in profiles.reasoning_options("gpt-5.5")],
            ["high"],
        )
        self.assertFalse(profiles.supports_reasoning_effort("gpt-5.5", "max"))


if __name__ == "__main__":
    unittest.main()
