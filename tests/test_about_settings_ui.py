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

    def test_about_section_contains_app_metadata_and_prismqml_link(self):
        page = self.read()

        self.assertIn('objectName: "aboutSettingsGroup"', page)
        self.assertIn('objectName: "aboutSettingsCard"', page)
        self.assertIn("Fluent.SettingsCardCore", page)
        self.assertIn('objectName: "aboutTitleLabel"', page)
        self.assertIn('text: "关于"', page)
        self.assertIn('objectName: "aboutVersionPrefix"', page)
        self.assertIn('objectName: "aboutDescriptionSuffix"', page)
        self.assertIn('objectName: "prismQmlHomepageLink"', page)
        self.assertIn("type: Fluent.Enums.label.type_hyperlink", page)
        self.assertIn("url: root.prismQmlHomepage", page)
        self.assertIn('text: "PrismQML"', page)
        self.assertNotIn("MessageBoxCore", page)
        self.assertNotIn('text: "版本信息"', page)

    def test_app_title_is_hyperlink_to_project_homepage(self):
        page = self.read()

        # 标题里的 ConfigPilot 取代原“项目主页”按钮承担跳转。
        self.assertIn('objectName: "projectHomepageLink"', page)
        self.assertIn('text: "ConfigPilot"', page)
        self.assertIn("url: root.appHomepage", page)
        self.assertIn("font.weight: Font.DemiBold", page)
        self.assertNotIn('objectName: "projectHomepageButton"', page)
        self.assertNotIn('text: "项目主页"', page)

    def test_update_action_merged_into_about_card(self):
        page = self.read()

        # “关于”与“检查更新”二合一：更新按钮占据原项目主页按钮位置。
        self.assertIn('objectName: "updateSettingsCard"', page)
        self.assertIn("autoUpdater.check()", page)
        self.assertIn("style: Fluent.Enums.button.style_default", page)
        self.assertIn("anchors.right: checkUpdateButton.left", page)
        self.assertNotIn('objectName: "applicationSettingsGroup"', page)
        self.assertNotIn('title: "应用"', page)
        self.assertNotIn("root.prismQmlVersion", page)

    def test_main_window_preserves_saved_language_and_binds_mica(self):
        main = (ROOT / "qml/main.qml").read_text(encoding="utf-8")

        self.assertIn('{ "text": "设置", "icon": iconPath("Settings"), "key": "AboutView" }', main)

        self.assertIn(
            'if (typeof ConfigManager === "undefined" || !ConfigManager)',
            main,
        )
        self.assertIn(
            "micaEnabled: typeof ConfigManager !== \"undefined\" && ConfigManager",
            main,
        )
        self.assertIn("? ConfigManager.micaEnabled : false", main)

    def test_prismqml_homepage_is_configured_and_injected(self):
        app_config = (ROOT / "app_config.json").read_text(encoding="utf-8")
        settings = (ROOT / "backend/app_settings.py").read_text(encoding="utf-8")
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        page = self.read()

        self.assertIn(
            '"prismqml_url": "https://github.com/aki-riko/PrismQML"',
            app_config,
        )
        self.assertIn('"project_url": "https://github.com/aki-riko/ConfigPilot"', app_config)
        self.assertIn('"author": "aki-riko"', app_config)
        self.assertIn('"year": 2026', app_config)
        self.assertIn('prismqml_url: str = ""', settings)
        self.assertIn('"PrismQMLHomepage", app_settings.prismqml_url', main)
        self.assertIn('"AppHomepage", app_settings.project_url', main)
        self.assertIn('"AppAuthor", app_settings.author', main)
        self.assertIn('"AppYear", app_settings.year', main)
        self.assertIn("PrismQMLHomepage", page)


if __name__ == "__main__":
    unittest.main()
