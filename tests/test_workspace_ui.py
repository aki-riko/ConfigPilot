from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceUiTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_shared_workspace_components_define_stable_responsive_layout(self):
        navigation = self.read("qml/components/TaskNavigation.qml")
        navigation_item = self.read("qml/components/TaskNavigationItem.qml")
        action_bar = self.read("qml/components/PageActionBar.qml")
        panel_scroll = self.read("qml/components/PanelScroll.qml")

        self.assertIn("property bool compact", navigation)
        self.assertIn("RowLayout", navigation)
        self.assertIn("Column", navigation)
        self.assertIn("signal activated(int index)", navigation)
        self.assertIn("required property int index", navigation_item)
        self.assertIn("required property var modelData", navigation_item)
        self.assertIn("implicitHeight: compact ? compactHeight : expandedHeight", navigation_item)
        self.assertIn("default property alias actions", action_bar)
        self.assertIn("default property alias panelContent", panel_scroll)

    def test_codex_uses_four_task_panels_with_persistent_actions(self):
        page = self.read("qml/views/CodexView.qml")

        for label in ("连接认证", "模型推理", "上下文", "兼容性"):
            self.assertIn(f'"title": "{label}"', page)
        self.assertEqual(page.count("PanelScroll {"), 4)
        self.assertIn('objectName: "codexSectionStack"', page)
        self.assertIn("currentIndex: root.selectedSection", page)
        self.assertIn("PageActionBar", page)
        self.assertIn("Fluent.Enums.icon.arrow_reset", page)
        self.assertIn("Fluent.Enums.icon.arrow_sync", page)
        self.assertIn("Fluent.Enums.icon.save", page)

    def test_claude_uses_three_task_panels_without_losing_backend_wiring(self):
        page = self.read("qml/views/ClaudeDesktopView.qml")

        for label in ("应用状态", "网关连接", "模型请求"):
            self.assertIn(f'"title": "{label}"', page)
        self.assertEqual(page.count("PanelScroll {"), 3)
        self.assertIn('objectName: "claudeSectionStack"', page)
        self.assertIn("ClaudeDesktopConfig.installProduct(product)", page)
        self.assertIn("ClaudeDesktopConfig.applyConfig", page)
        self.assertIn("PageActionBar", page)

    def test_about_page_is_scannable_and_keeps_update_action(self):
        page = self.read("qml/views/AboutView.qml")

        self.assertIn("PageHeader", page)
        self.assertIn('text: "Codex CLI"', page)
        self.assertIn('text: "Claude Desktop"', page)
        self.assertIn('text: "写入与恢复"', page)
        self.assertIn('objectName: "checkForUpdatesButton"', page)
        self.assertIn("autoUpdater.check()", page)
        self.assertNotIn("displayLarge", page)


if __name__ == "__main__":
    unittest.main()
