from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClaudeDesktopUiTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_backend_is_registered_and_navigation_opens_new_page(self):
        main_py = self.read("main.py")
        main_qml = self.read("qml/main.qml")

        self.assertIn("ClaudeDesktopConfig", main_py)
        self.assertIn(
            'setContextProperty("ClaudeDesktopConfig", claude_desktop)', main_py
        )
        self.assertIn('"text": "Claude"', main_qml)
        self.assertIn('Qt.resolvedUrl("views/ClaudeDesktopView.qml")', main_qml)

    def test_page_wires_gateway_sensitive_fields_and_status_sections(self):
        page = self.read("qml/views/ClaudeDesktopView.qml")
        status = self.read("qml/views/ClaudeStatusSection.qml")
        gateway = self.read("qml/views/ClaudeGatewaySection.qml")
        advanced = self.read("qml/views/ClaudeAdvancedSection.qml")

        for component in (
            "ClaudeStatusSection",
            "ClaudeGatewaySection",
            "ClaudeAdvancedSection",
        ):
            self.assertIn(component, page)
        self.assertIn("ClaudeDesktopConfig.applyConfig", page)
        self.assertIn('"clearApiKey": fClearApiKey', page)
        self.assertIn('"clearHeaders": fClearHeaders', page)
        self.assertIn("完全退出并重新打开 Claude Desktop", page)
        self.assertIn(
            'text: root.configBusy ? "处理中..." : "启用并应用"',
            page,
        )
        self.assertIn("ClaudeDesktopConfig.operationBusy", page)
        for component in ("ClaudeGatewaySection", "ClaudeAdvancedSection"):
            self.assertRegex(
                page,
                re.compile(
                    rf"{component}\s*\{{.*?enabled:\s*!root\.configBusy",
                    re.DOTALL,
                ),
            )

        self.assertIn("columns: width < 700 ? 1 : 2", status)
        self.assertIn("id: statusGrid", status)
        self.assertIn("columns: width < 480 ? 1 : 3", status)
        self.assertIn("uniformCellWidths: columns === 3", status)
        self.assertIn("readonly property real equalItemWidth", status)
        self.assertEqual(
            status.count("Layout.preferredWidth: statusGrid.equalItemWidth"), 3
        )
        self.assertEqual(
            status.count("Layout.maximumWidth: statusGrid.equalItemWidth"), 3
        )
        self.assertIn("Layout.preferredWidth: summaryLayout.columns === 2", status)
        self.assertIn("summaryLayout.width - 240", status)
        self.assertIn('text: "Claude Desktop"', status)
        self.assertEqual(status.count("Fluent.Toggle"), 2)
        self.assertIn('objectName: "claudeDeveloperModeToggle"', status)
        self.assertIn('objectName: "claudeGatewayToggle"', status)
        self.assertIn("signal developerModeToggled(bool value)", status)
        self.assertIn("signal gatewayToggled(bool value)", status)
        self.assertIn("ClaudeDesktopConfig.setDeveloperModeEnabled(value)", page)
        self.assertIn("ClaudeDesktopConfig.setThirdPartyEnabled(value)", page)
        self.assertIn("Fluent.Enums.button.feature_dropdown", status)
        self.assertIn('objectName: "claudeInstallDropdown"', status)
        self.assertIn('"text": "Claude Code CLI"', status)
        self.assertIn("Claude Desktop 官网版", status)
        self.assertIn("Layout.maximumWidth: 240", status)
        self.assertIn("signal installRequested(string product)", status)
        self.assertIn("signal cancelInstallRequested()", status)
        self.assertIn("Fluent.ProgressBar", status)
        self.assertIn("ClaudeDesktopConfig.installProduct(product)", page)
        self.assertIn("ClaudeDesktopConfig.cancelInstall()", page)
        self.assertIn("ClaudeDesktopConfig.installProgress", page)

        self.assertIn("Authorization: Bearer", gateway)
        self.assertIn("x-api-key", gateway)
        self.assertIn("自动补全 /v1", gateway)
        self.assertIn("type_password", gateway)
        self.assertIn("留空保持不变", gateway)

        self.assertIn("/v1/models", advanced)
        self.assertIn("Fluent.Expander", advanced)
        self.assertIn("columns: width < 680 ? 1 : 2", advanced)
        self.assertIn("输入 JSON 对象覆盖现有值", advanced)
        self.assertIn("敏感内容不会回显", advanced)


if __name__ == "__main__":
    unittest.main()
