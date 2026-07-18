import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_public_branding_has_no_obsolete_product_names(self):
        public_files = [
            "README.md",
            "main.py",
            "requirements.txt",
            "qml/main.qml",
            "qml/views/AboutView.qml",
            "qml/views/CodexView.qml",
            "qml/views/ConnectionSection.qml",
            "qml/views/ModelSection.qml",
            "qml/views/ContextSection.qml",
            "qml/views/AdvancedSection.qml",
            "build_nuitka.cmd",
            "scripts/build_macos.sh",
            ".github/workflows/build.yml",
        ]
        obsolete_markers = [
            "quicksketch",
            "Codex 配置助手",
            "CodexConfig.exe",
            "CodexConfig_Setup",
            "life.9li.codexconfig",
            "PrismQML 速写 Demo",
        ]

        for relative_path in public_files:
            content = self.read(relative_path)
            for marker in obsolete_markers:
                self.assertNotIn(marker, content, f"{relative_path} 仍包含 {marker}")

    def test_packaging_uses_configpilot_brand(self):
        self.assertFalse((ROOT / "CodexConfig.iss").exists())

        installer = self.read("ConfigPilot.iss")
        self.assertIn('#define AppName "ConfigPilot"', installer)
        self.assertIn('#define AppExe "ConfigPilot.exe"', installer)
        self.assertIn("OutputBaseFilename=ConfigPilot_Setup_{#AppVer}", installer)

        windows_build = self.read("build_nuitka.cmd")
        self.assertIn("--output-filename=ConfigPilot.exe", windows_build)
        self.assertIn("--product-name=ConfigPilot", windows_build)
        self.assertIn(
            "--include-data-files=model_profiles.json=model_profiles.json",
            windows_build,
        )
        self.assertIn(
            "--include-data-files=app_config.json=app_config.json",
            windows_build,
        )

        macos_build = self.read("scripts/build_macos.sh")
        self.assertIn('APP_NAME="ConfigPilot"', macos_build)
        self.assertIn("life.9li.configpilot", macos_build)

    def test_installer_preserves_upgrade_identity_and_cleans_legacy_files(self):
        installer = self.read("ConfigPilot.iss")
        self.assertIn("AppId={{8F3C2A91-CODEX-9LI-CONF-000000000001}", installer)
        self.assertIn('[InstallDelete]', installer)
        self.assertIn('#define AppLegacyName "Codex 配置助手"', installer)
        self.assertIn('#define LegacyAppExe "CodexConfig.exe"', installer)
        self.assertIn('#define LegacyInstallDirName "CodexConfig"', installer)
        self.assertIn("UsePreviousAppDir=no", installer)
        self.assertIn("UsePreviousGroup=no", installer)
        self.assertIn("IsOwnedLegacyInstallDir", installer)
        self.assertIn("if CurStep <> ssPostInstall then", installer)
        self.assertIn("保留非标准旧安装目录", installer)

    def test_windows_shortcuts_match_prismqml_app_user_model_id(self):
        installer = self.read("ConfigPilot.iss")
        main = self.read("main.py")

        self.assertIn('#define AppUserModelID "PrismQML.ConfigPilot"', installer)
        self.assertEqual(installer.count('AppUserModelID: "{#AppUserModelID}"'), 2)
        self.assertIn('if "__compiled__" in globals():', main)
        self.assertIn(
            'os.environ.setdefault("PRISMQML_APP_USER_MODEL_ID", "PrismQML.ConfigPilot")',
            main,
        )
        self.assertLess(
            main.index('if "__compiled__" in globals():'),
            main.index("from prismqml import App"),
        )
        self.assertIn("app.setWindowIcon(taskbar_icon)", main)

    def test_icon_sources_are_valid_and_windows_icon_has_multiple_sizes(self):
        png = (ROOT / "resources" / "app_icon.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (2048, 2048))
        self.assertEqual((png[24], png[25]), (8, 6))

        main = self.read("main.py")
        self.assertIn(
            '"app_icon.ico" if sys.platform == "win32" else "app_icon.png"',
            main,
        )
        self.assertIn(
            'logo_path = os.path.join(app_dir, "resources", "app_icon.png")',
            main,
        )
        self.assertIn('window_instance.setIcon(taskbar_icon)', main)
        for script in (
            "scripts/make_ico.py",
            "scripts/make_icns.py",
            "scripts/make_social_preview.py",
        ):
            content = self.read(script)
            self.assertIn('"app_icon.png"', content)
            self.assertNotIn('"app_icon.svg"', content)

        ico = (ROOT / "resources" / "app_icon.ico").read_bytes()
        reserved, image_type, image_count = struct.unpack("<HHH", ico[:6])
        self.assertEqual((reserved, image_type), (0, 1))
        self.assertGreaterEqual(image_count, 7)

    def test_navigation_uses_bundled_product_icons(self):
        main_qml = self.read("qml/main.qml")
        self.assertIn('resourceIconPath("chatgpt")', main_qml)
        self.assertIn('resourceIconPath("claude")', main_qml)

        for icon_name in ("chatgpt.svg", "claude.svg"):
            icon = self.read(f"resources/{icon_name}")
            self.assertIn("<svg", icon)
            self.assertIn("viewBox=", icon)

    def test_documentation_images_have_expected_dimensions(self):
        expected_dimensions = {
            "docs/images/configpilot-main.png": (980, 640),
            "docs/images/social-preview.png": (1280, 640),
        }
        for relative_path, expected in expected_dimensions.items():
            png = (ROOT / relative_path).read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", png[16:24]), expected)

    def test_responsive_sections_replace_fixed_width_form(self):
        view = self.read("qml/views/CodexView.qml")
        connection = self.read("qml/views/ConnectionSection.qml")
        model = self.read("qml/views/ModelSection.qml")
        context = self.read("qml/views/ContextSection.qml")
        advanced = self.read("qml/views/AdvancedSection.qml")

        self.assertNotIn('text: "选择中转"', view)
        self.assertNotIn("id: presetBox", view)
        self.assertIn("anchors.bottom: actionBar.top", view)
        self.assertIn("ConnectionSection", view)
        self.assertIn("ModelSection", view)
        self.assertIn("ContextSection", view)
        self.assertIn("AdvancedSection", view)
        self.assertIn("highestReasoningEffortForModel", view)

        for section in (connection, model, context):
            self.assertIn("import QtQuick.Layouts", section)
            self.assertIn("GridLayout", section)
            self.assertIn("columns: width <", section)

        self.assertIn("未包含 /v1 时自动补全", connection)
        self.assertIn('text: "套用稳定上下文"', context)
        self.assertNotIn("feature: Fluent.Enums.button.feature_dropdown", context)
        self.assertIn("Fluent.Expander", advanced)

    def test_latest_prismqml_engine_is_pinned(self):
        requirements = self.read("requirements.txt")
        about = self.read("qml/views/AboutView.qml")
        main = self.read("qml/main.qml")

        self.assertIn("prismqml==0.2.24.13", requirements)
        self.assertIn("AppUpdater.prismqmlVersion", about)
        self.assertIn("minimumWidth: 760", main)
        self.assertIn("minimumHeight: 560", main)

    def test_release_version_and_macos_disclosure_are_consistent(self):
        version = "1.0.14"
        app_config = self.read("app_config.json")
        self.assertIn(f'"version": "{version}"', app_config)
        self.assertIn(f'set "APP_VER={version}"', self.read("build_nuitka.cmd"))
        self.assertIn(f'#define AppVer "{version}"', self.read("ConfigPilot.iss"))

        workflow = self.read(".github/workflows/build.yml")
        self.assertIn(f'default: "{version}"', workflow)
        self.assertIn(f"github.event.inputs.app_ver || '{version}'", workflow)

        readme = self.read("README.md")
        macos_build = self.read("scripts/build_macos.sh")
        first_open = self.read("docs/macos-first-open.txt")
        release_notes = self.read("docs/release-notes/v1.0.14.md")

        for content in (readme, first_open, release_notes):
            self.assertIn("Apple Developer Program", content)
            self.assertIn("xattr -dr com.apple.quarantine", content)
            self.assertIn("Apple Silicon", content)

        self.assertIn(
            'cp "docs/macos-first-open.txt" "$STAGING/首次打开说明.txt"',
            macos_build,
        )

    def test_application_update_flow_uses_prismqml_engine(self):
        main_py = self.read("main.py")
        updater_py = self.read("backend/app_updater.py")
        main_qml = self.read("qml/main.qml")
        about_qml = self.read("qml/views/AboutView.qml")
        installer = self.read("ConfigPilot.iss")

        self.assertIn('setContextProperty("AppUpdater", app_updater)', main_py)
        self.assertIn("parent=app.qapp", main_py)
        self.assertIn("BackgroundDownloadUpdater", updater_py)
        self.assertIn("AppUpdater.checkAutomatically()", main_qml)
        self.assertIn("Fluent.UpdateDialog", main_qml)
        self.assertIn("Fluent.ProgressDialog", main_qml)
        self.assertIn("AppUpdater.downloadUpdate", main_qml)
        self.assertIn("AppUpdater.checkManually()", about_qml)
        self.assertIn("/AUTORESTARTAPP", installer)


if __name__ == "__main__":
    unittest.main()
