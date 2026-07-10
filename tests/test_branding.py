import struct
import unittest
import xml.etree.ElementTree as ET
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

        macos_build = self.read("scripts/build_macos.sh")
        self.assertIn('APP_NAME="ConfigPilot"', macos_build)
        self.assertIn("life.9li.configpilot", macos_build)

    def test_installer_preserves_upgrade_identity_and_cleans_legacy_files(self):
        installer = self.read("ConfigPilot.iss")
        self.assertIn("AppId={{8F3C2A91-CODEX-9LI-CONF-000000000001}", installer)
        self.assertIn('[InstallDelete]', installer)
        self.assertIn('#define AppLegacyName "Codex 配置助手"', installer)
        self.assertIn('#define LegacyAppExe "CodexConfig.exe"', installer)

    def test_icon_sources_are_valid_and_windows_icon_has_multiple_sizes(self):
        svg_path = ROOT / "resources" / "app_icon.svg"
        svg_root = ET.parse(svg_path).getroot()
        self.assertTrue(svg_root.tag.endswith("svg"))
        self.assertIn("configpilot-gradient", svg_path.read_text(encoding="utf-8"))

        ico = (ROOT / "resources" / "app_icon.ico").read_bytes()
        reserved, image_type, image_count = struct.unpack("<HHH", ico[:6])
        self.assertEqual((reserved, image_type), (0, 1))
        self.assertGreaterEqual(image_count, 7)

    def test_documentation_images_have_expected_dimensions(self):
        expected_dimensions = {
            "docs/images/configpilot-main.png": (980, 640),
            "docs/images/social-preview.png": (1280, 640),
        }
        for relative_path, expected in expected_dimensions.items():
            png = (ROOT / relative_path).read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", png[16:24]), expected)


if __name__ == "__main__":
    unittest.main()
