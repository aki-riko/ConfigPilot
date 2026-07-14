from pathlib import Path
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
        self.assertIn('text: "启用并应用"', page)

        self.assertIn("columns: width < 700 ? 2 : 4", status)
        self.assertIn('text: "Claude Desktop"', status)

        self.assertIn("Authorization: Bearer", gateway)
        self.assertIn("x-api-key", gateway)
        self.assertIn("type_password", gateway)
        self.assertIn("留空保持不变", gateway)

        self.assertIn("/v1/models", advanced)
        self.assertIn("Fluent.Expander", advanced)
        self.assertIn("columns: width < 680 ? 1 : 2", advanced)
        self.assertIn("输入 JSON 对象覆盖现有值", advanced)
        self.assertIn("敏感内容不会回显", advanced)


if __name__ == "__main__":
    unittest.main()
