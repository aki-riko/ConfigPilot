from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AboutSettingsUiTests(unittest.TestCase):
    def read(self):
        return (ROOT / "qml/views/AboutView.qml").read_text(encoding="utf-8")

    def test_help_page_uses_gitora_style_basic_settings_cards(self):
        page = self.read()

        self.assertIn("Fluent.SettingsCardGroup", page)
        self.assertIn('objectName: "basicSettingsGroup"', page)
        for object_name in (
            "themeSettingsCard",
            "skinSettingsCard",
            "micaSettingsCard",
            "languageSettingsCard",
        ):
            self.assertIn(f'objectName: "{object_name}"', page)

        for contract in (
            "root.configManager.themeOptions",
            "root.configManager.skinOptions",
            "root.configManager.setTheme",
            "root.configManager.setSkin",
            "root.configManager.micaEnabled",
            "root.configManager.setMicaEnabled",
            "Fluent.Translator.setLanguage",
        ):
            self.assertIn(contract, page)

    def test_current_explanation_is_presented_by_messagebox(self):
        page = self.read()

        self.assertIn("Fluent.MessageBox", page)
        self.assertIn('objectName: "messageBoxCoreAboutDialog"', page)
        self.assertIn('title: "关于 MessageBoxCore"', page)
        self.assertIn("content: root.aboutMessage", page)
        self.assertIn("底层 DialogBoxCore", page)
        self.assertIn("overlayTarget: root.Window.window", page)
        self.assertIn('objectName: "messageBoxCoreAboutCard"', page)
        self.assertIn("onClicked: messageBoxCoreAboutDialog.open()", page)
        self.assertIn('cancelButtonVisible: false', page)
        self.assertNotIn('text: "ConfigPilot 做什么"', page)

    def test_update_and_version_remain_separate_from_the_explanation(self):
        page = self.read()

        self.assertIn('objectName: "applicationSettingsGroup"', page)
        self.assertIn('objectName: "updateSettingsCard"', page)
        self.assertIn('objectName: "versionSettingsGroup"', page)
        self.assertIn("autoUpdater.check()", page)
        self.assertIn("root.prismQmlVersion", page)

    def test_main_window_preserves_saved_language_and_binds_mica(self):
        main = (ROOT / "qml/main.qml").read_text(encoding="utf-8")

        self.assertIn(
            'if (typeof ConfigManager === "undefined" || !ConfigManager)',
            main,
        )
        self.assertIn(
            "micaEnabled: typeof ConfigManager !== \"undefined\" && ConfigManager",
            main,
        )
        self.assertIn("? ConfigManager.micaEnabled : false", main)


if __name__ == "__main__":
    unittest.main()
