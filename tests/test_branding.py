import json
import os
import re
import subprocess
import struct
import sys
import tempfile
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
        for component in (
            "ConnectionSection",
            "ModelSection",
            "ContextSection",
            "AdvancedSection",
        ):
            self.assertRegex(
                view,
                re.compile(
                    rf"{component}\s*\{{.*?enabled:\s*!root\.configBusy",
                    re.DOTALL,
                ),
            )

        for section in (connection, model, context):
            self.assertIn("import QtQuick.Layouts", section)
            self.assertIn("GridLayout", section)
            self.assertIn("columns: width <", section)

        self.assertIn("未包含 /v1 时自动补全", connection)
        self.assertIn('objectName: "authJsonInput"', connection)
        self.assertIn('objectName: "authJsonImportButton"', connection)
        self.assertIn('objectName: "refreshChatgptAuthButton"', connection)
        self.assertIn("importAuthJson", view)
        self.assertIn("refreshChatgptAuth", view)
        self.assertIn('text: "套用稳定上下文"', context)
        self.assertNotIn("feature: Fluent.Enums.button.feature_dropdown", context)
        self.assertIn("Fluent.Expander", advanced)
        self.assertIn("function commitKey()", connection)
        self.assertIn("onAccepted: root.commitKey()", connection)
        self.assertIn("onEditingFinished: root.commitKey()", connection)
        self.assertIn("输入完成后自动保存", connection)
        self.assertIn("connectionSection.keyDraft.trim()", view)
        self.assertIn("CodexConfig.setKey(key)", view)

    def test_latest_prismqml_engine_is_pinned(self):
        requirements = self.read("requirements.txt")
        about = self.read("qml/views/AboutView.qml")
        main = self.read("qml/main.qml")

        self.assertIn("prismqml==0.4.0.8", requirements)
        self.assertIn("PrismQMLVersion", about)
        self.assertIn("minimumWidth: 760", main)
        self.assertIn("minimumHeight: 560", main)

    def test_prismqml_config_is_owned_by_configpilot(self):
        main = self.read("main.py")
        settings = self.read("backend/app_settings.py")

        self.assertIn("config_path=resolve_prismqml_config_path()", main)
        self.assertIn("persist_appearance=True", main)
        self.assertIn('_APPLICATION_CONFIG_DIR_NAME = "ConfigPilot"', settings)
        self.assertIn('_PRISMQML_CONFIG_FILE_NAME = "prismqml.json"', settings)

    def test_startup_splash_uses_engine_owned_instance(self):
        main_qml = self.read("qml/main.qml")

        self.assertIn('splashSubtitle: "正在加载..."', main_qml)
        self.assertNotIn("_splashInstance = root.splashComponent.createObject", main_qml)
        self.assertNotIn("property Component splashComponent", main_qml)

    def test_configpilot_config_wins_when_gallery_config_exists(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            gallery_path = temporary_root / "gallery.json"
            configpilot_path = (
                temporary_root / "local" / "ConfigPilot" / "prismqml.json"
            )
            configpilot_path.parent.mkdir(parents=True)
            gallery_path.write_text(
                json.dumps(
                    {
                        "Appearance": {
                            "Theme": "dark",
                            "Skin": "vintage_ticket",
                            "Language": "zh_CN",
                            "AccentColor": "#123456",
                        }
                    }
                ),
                encoding="utf-8",
            )
            configpilot_path.write_text(
                json.dumps(
                    {
                        "Appearance": {
                            "Theme": "light",
                            "Skin": "fluent",
                            "Language": "en",
                            "AccentColor": "#654321",
                        }
                    }
                ),
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "LOCALAPPDATA": str(temporary_root / "local"),
                    "PRISMQML_CONFIG_FILE": str(gallery_path),
                    "PYTHONIOENCODING": "utf-8",
                    "QT_QPA_PLATFORM": "offscreen",
                }
            )
            script = """
from pathlib import Path
from PySide6.QtCore import QTimer
from backend.app_settings import resolve_prismqml_config_path
from prismqml import App
from prismqml.python.config import getConfigManager

config_path = resolve_prismqml_config_path()
app = App([], config_path=config_path, persist_appearance=True)
manager = getConfigManager(config_path, persist_appearance=True)
assert Path(manager.getConfigPath()).resolve() == config_path.resolve()
assert manager.theme == "light"
assert manager.skin == "fluent"
assert manager.language == "en"
assert manager.accentColor == "#654321"
QTimer.singleShot(0, app.quit)
raise SystemExit(app.exec())
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_version_and_macos_disclosure_are_consistent(self):
        version = "1.0.25"
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
        release_notes = self.read("docs/release-notes/v1.0.25.md")

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
        main_qml = self.read("qml/main.qml")
        about_qml = self.read("qml/views/AboutView.qml")
        installer = self.read("ConfigPilot.iss")

        self.assertIn("app.enable_auto_update(", main_py)
        self.assertIn('setContextProperty("AppUpdater", app_updater)', main_py)
        self.assertIn("Fluent.AutoUpdater", main_qml)
        self.assertIn("Fluent.AutoUpdaterProgressDialogPresenter", main_qml)
        self.assertIn("autoUpdater.checkSilently()", main_qml)
        self.assertIn("Fluent.AutoUpdater", about_qml)
        self.assertIn("autoUpdater.check()", about_qml)
        self.assertIn("/AUTORESTARTAPP", installer)


if __name__ == "__main__":
    unittest.main()
