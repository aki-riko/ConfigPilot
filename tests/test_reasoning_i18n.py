import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReasoningI18nTests(unittest.TestCase):
    def test_max_uses_app_i18n_and_ultra_is_not_configurable(self):
        selector = (ROOT / "qml/views/ReasoningEffortSelector.qml").read_text(
            encoding="utf-8"
        )
        translations = (ROOT / "qml/i18n/ConfigPilotI18n.js").read_text(
            encoding="utf-8"
        )
        profiles = json.loads(
            (ROOT / "model_profiles.json").read_text(encoding="utf-8")
        )

        self.assertIn('AppI18n.tr("reasoning_max", activeLanguage())', selector)
        self.assertIn('"reasoning_max": "MAX"', translations)
        self.assertIn('"reasoning_max": "最高"', translations)
        self.assertNotIn("ultra", json.dumps(profiles, ensure_ascii=False).lower())


if __name__ == "__main__":
    unittest.main()
