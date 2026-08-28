from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SettingsUiTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_settings_is_a_first_class_navigation_page(self):
        main = self.read("qml/main.qml")
        settings = self.read("qml/views/SettingsView.qml")

        self.assertIn('"text": "设置"', main)
        self.assertIn('"key": "SettingsView"', main)
        self.assertIn('Qt.resolvedUrl("views/SettingsView.qml")', main)
        self.assertIn("micaEnabled: ConfigManager ? ConfigManager.micaEnabled : false", main)
        self.assertIn('objectName: "settingsView"', settings)
        self.assertIn("PageScaffold", settings)
        self.assertIn("PageHeader", settings)
        self.assertIn("Fluent.SettingsCardGroup", settings)

    def test_settings_wires_persistent_appearance_and_update_actions(self):
        settings = self.read("qml/views/SettingsView.qml")

        for contract in (
            "ConfigManager.themeOptions",
            "ConfigManager.setTheme",
            "ConfigManager.skinOptions",
            "ConfigManager.setSkin",
            "ConfigManager.micaEnabled",
            "ConfigManager.setMicaEnabled",
            "Fluent.Translator.setLanguage",
            "root.autoUpdater.check()",
            'Window.window.navigateTo("AboutView")',
            'objectName: "themeSettingsCard"',
            'objectName: "skinSettingsCard"',
            'objectName: "updateSettingsCard"',
        ):
            self.assertIn(contract, settings)

    def test_all_primary_pages_use_the_same_scaffold(self):
        for view in (
            "qml/views/CodexView.qml",
            "qml/views/ClaudeDesktopView.qml",
            "qml/views/AboutView.qml",
        ):
            source = self.read(view)
            self.assertIn('import "../components"', source)
            self.assertIn("PageScaffold", source)
            self.assertIn("PageHeader", source)


if __name__ == "__main__":
    unittest.main()
