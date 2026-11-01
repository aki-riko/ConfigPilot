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
        self.assertIn("Fluent.Expander", connection)
        self.assertIn('title: "连接与认证"', connection)
        self.assertIn('content: ""', connection)
        self.assertIn("icon: Fluent.Enums.icon.server", connection)
        self.assertIn("Fluent.Expander", model)
        self.assertIn('title: "模型与推理"', model)
        self.assertIn("icon: Fluent.Enums.icon.brain", model)
        self.assertIn("Fluent.Expander", context)
        self.assertIn('title: "上下文预算"', context)
        self.assertIn("icon: Fluent.Enums.icon.data_usage", context)
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
        # 凭据两种来源改成分段控件切换，不再上下堆叠。
        self.assertIn('objectName: "codexCredentialTabs"', connection)
        self.assertIn("Fluent.SegmentedControl", connection)
        self.assertIn("credentialTabs.currentIndex === 0", connection)
        self.assertIn("credentialTabs.currentIndex === 1", connection)
        # 「修复中转站 401」这类维护操作已移进工具箱外抽屉。
        self.assertNotIn('objectName: "repairRelayAuthButton"', connection)
        self.assertIn("signal repairRelayAuthRequested", connection)
        self.assertIn("enabled: !root.configBusy", connection)
        self.assertIn("Fluent.Enums.input.type_password", connection)
        self.assertIn("importAuthJson", view)
        self.assertIn("repairRelayAuth", view)
        self.assertIn('text: "套用稳定上下文"', context)
        self.assertIn('text: "套用百万上下文"', context)
        self.assertNotIn("feature: Fluent.Enums.button.feature_dropdown", context)
        self.assertIn("Fluent.Expander", advanced)
        self.assertIn("function commitKey()", connection)
        self.assertIn("onAccepted: root.commitKey()", connection)
        self.assertIn("onEditingFinished: root.commitKey()", connection)
        # 密钥用 PrismQML 内置的密码框：type_password 自带眼睛按钮并切换
        # showPassword，不得在外部再叠一个显隐按钮（否则会出现两个眼睛）。
        self.assertIn("property string keyValue", connection)
        self.assertIn("Fluent.Enums.input.type_password", connection)
        self.assertNotIn("keyRevealed", connection)
        self.assertNotIn("codexKeyRevealButton", connection)
        self.assertIn("text = root.keyValue", connection)
        self.assertIn("text = root.keyValue", connection)
        self.assertNotIn("保存密钥", connection)
        self.assertNotIn("saveKeyRequested", connection)
        self.assertIn('objectName: "codexApiKeyEdit"', connection)
        self.assertIn("connectionSection.keyDraft.trim()", view)
        self.assertIn('"key": key', view)
        self.assertIn("CodexConfig.authKeyPreview", view)

    def test_all_pages_use_constrained_content_and_compact_actions(self):
        codex = self.read("qml/views/CodexView.qml")
        claude = self.read("qml/views/ClaudeDesktopView.qml")
        about = self.read("qml/views/AboutView.qml")
        connection = self.read("qml/views/ConnectionSection.qml")
        toolbox = self.read("qml/views/ToolboxDrawer.qml")
        model = self.read("qml/views/ModelSection.qml")
        context = self.read("qml/views/ContextSection.qml")
        status = self.read("qml/views/ClaudeStatusSection.qml")

        for page in (codex, claude, about):
            self.assertIn("contentMaxWidth", page)
            self.assertIn("padding: Fluent.Enums.spacing.none", page)
            self.assertIn("orientation: Qt.Vertical", page)
            self.assertIn("font.pixelSize: Fluent.Enums.typography.display", page)

        for content in (codex, claude):
            self.assertIn("Math.min(", content)
            self.assertIn("implicitHeight: pageColumn.implicitHeight", content)

        for content, width in (
            (codex, "Layout.maximumWidth: 128"),
            (claude, "Layout.maximumWidth: 220"),
            # 维护按钮已收进工具箱抽屉，固定宽度约束随之落在抽屉里。
            (toolbox, "Layout.maximumWidth: 88"),
            (model, "Layout.maximumWidth: 112"),
            (context, "Layout.maximumWidth: 152"),
            (status, "Layout.maximumWidth: 220"),
        ):
            self.assertIn(width, content)

        # 页脚高度绑定在 root.controlHeight 上：页面若未声明该属性，QML 得到
        # undefined + 数值 = NaN，actionBar 高度归零，整条页脚会静默消失。
        for page_name, page in (
            ("CodexView.qml", codex),
            ("ClaudeDesktopView.qml", claude),
        ):
            if "root.controlHeight" in page:
                self.assertIn(
                    "readonly property int controlHeight: "
                    "Fluent.Enums.controlSize.buttonHeight",
                    page,
                    f"{page_name} 使用了 root.controlHeight 但未声明该属性",
                )
                self.assertIn(
                    "height: root.controlHeight + 2 * Fluent.Enums.spacing.",
                    page,
                    f"{page_name} 的操作栏高度未使用 controlHeight",
                )

        self.assertIn('icon: Fluent.Enums.icon.save', codex)
        self.assertIn('icon: Fluent.Enums.icon.arrow_import', connection)
        self.assertIn('icon: Fluent.Enums.icon.copy', status)
        # 维护操作已全部移进外抽屉：页面上不再横铺这些按钮。
        for gone in (
            "repairRelayAuthButton",
            "sandboxStopgapButton",
            "restoreInitialButton",
            "repairSubagentDefaultsButton",
        ):
            self.assertNotIn(f'objectName: "{gone}"', codex)
            self.assertNotIn(f'objectName: "{gone}"', connection)
        self.assertIn('objectName: "codexToolboxButton"', codex)
        self.assertIn("codexToolbox.open()", codex)

    def test_latest_prismqml_engine_is_pinned(self):
        requirements = self.read("requirements.txt")
        main = self.read("qml/main.qml")

        self.assertIn("prismqml==0.5.0.23", requirements)
        self.assertIn('setContextProperty("PrismQMLVersion", prismqml.__version__)', self.read("main.py"))
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
        main_py = self.read("main.py")

        self.assertIn('splashSubtitle: "正在加载..."', main_qml)
        self.assertNotIn("_splashInstance = root.splashComponent.createObject", main_qml)
        self.assertNotIn("property Component splashComponent", main_qml)
        self.assertIn("application_icon=taskbar_icon_path", main_py)
        self.assertIn('splash_subtitle="正在加载..."', main_py)
        self.assertIn("splash_width=APP_WINDOW_WIDTH", main_py)
        self.assertIn("splash_height=APP_WINDOW_HEIGHT", main_py)
        self.assertIn('app.attach_startup_window(window_instance)', main_py)
        self.assertIn("visible: false", main_qml)

    def test_windows_default_pages_only_receive_visual_items(self):
        main_qml = self.read("qml/main.qml")

        self.assertIn("property Component updateProgressPresenter", main_qml)
        self.assertIn("property QtObject autoUpdater", main_qml)
        self.assertIn("property Item updateLayer", main_qml)

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
        version = "1.0.35"
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
        release_notes = self.read("docs/release-notes/v1.0.35.md")

        for content in (readme, first_open, release_notes):
            self.assertIn("Apple Developer Program", content)
            self.assertIn("xattr -dr com.apple.quarantine", content)
            self.assertIn("Apple Silicon", content)

        self.assertIn(
            'cp "docs/macos-first-open.txt" "$STAGING/首次打开说明.txt"',
            macos_build,
        )

    def test_section_cards_size_by_implicit_height_not_children_rect(self):
        """卡片内容容器必须按 implicitHeight 取高，不能用 childrenRect。

        Column 的 implicitHeight 含 left/right/top/bottom padding，而
        childrenRect.height 不含。历史上 ConnectionSection / ModelSection /
        ContextSection / ClaudeGatewaySection / ClaudeStatusSection /
        ClaudeAdvancedSection 都用 ``height: childrenRect.height``，导致
        卡片底部固定少 padding 那么多像素，最后一行被裁掉。
        """
        for relative_path in (
            "qml/views/ConnectionSection.qml",
            "qml/views/ModelSection.qml",
            "qml/views/ContextSection.qml",
            "qml/views/AdvancedSection.qml",
            "qml/views/ClaudeGatewaySection.qml",
            "qml/views/ClaudeStatusSection.qml",
            "qml/views/ClaudeAdvancedSection.qml",
        ):
            content = self.read(relative_path)
            self.assertNotIn(
                "height: childrenRect.height",
                content,
                f"{relative_path} 用 childrenRect 算高度会裁掉卡片底部",
            )
            self.assertRegex(
                content,
                re.compile(r"implicitHeight:\s*\w+\.implicitHeight"),
                f"{relative_path} 未按 implicitHeight 取高",
            )

    def test_form_fields_share_one_label_spec(self):
        """字段标签走统一 FormField，不再每个 Section 各写一套双层头。"""
        form_field = self.read("qml/views/FormField.qml")
        self.assertIn("property string label", form_field)
        self.assertIn("property string keyName", form_field)
        self.assertIn("property string hint", form_field)
        # Layout 里引用自身宽度会触发 Qt Quick Layouts 递归重排，
        # 标签上限必须是常量。
        self.assertIn("Layout.maximumWidth: 280", form_field)

        for relative_path in (
            "qml/views/ConnectionSection.qml",
            "qml/views/ModelSection.qml",
            "qml/views/ContextSection.qml",
            "qml/views/ClaudeGatewaySection.qml",
            "qml/views/ClaudeAdvancedSection.qml",
            "qml/views/ClaudeModelEntry.qml",
        ):
            content = self.read(relative_path)
            self.assertIn("FormField {", content, f"{relative_path} 未使用 FormField")
            self.assertNotIn(
                'text: "provider"',
                content,
                f"{relative_path} 仍保留旧的双层键名标签",
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
