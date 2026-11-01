# coding: utf-8
"""布局重构的真行为测试：在真实 QQuickWindow 里实例化 Section 并量几何。

源码断言只能防「写法回退」，拦不住 QML 布局在容器里算出 0 高/0 宽
（Qt Quick Layouts 递归重排、childrenRect 不含 padding、宽度循环绑定等）。
这里用 offscreen 真实窗口实例化，直接对着渲染后的几何做断言。
"""

import os
import sys
import time
import unittest
from pathlib import Path

import prismqml
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIEWS_DIR = ROOT / "qml" / "views"

from tests.qt_test_utils import APP  # noqa: E402


# Section 实例化时只读取这些后端属性/方法；给最小替身即可，不发网络请求。
STUB = """
import QtQuick

QtObject {
    property string configPath: "/tmp/config.toml"
    property string provider: "relay"
    property string baseUrl: "https://api.example.com/v1"
    property string wireApi: "responses"
    property string model: "gpt-5.6-sol"
    property bool requiresAuth: false
    property string reasoningEffort: "high"
    property bool disableStorage: false
    property string modelContextWindow: "400000"
    property string modelAutoCompactTokenLimit: "320000"
    property string toolOutputTokenLimit: "6000"
    property bool hasKey: true
    property bool hasChatgptAuth: false
    property string authSource: "auth_json"
    property string envKey: "OPENAI_API_KEY"
    property bool envKeyPresent: true
    property bool authReady: true
    property bool operationBusy: false
    property bool modelsLoading: false
    property bool hasRestorableChanges: false
    property int profilesRevision: 0

    function normalizedBaseUrl(value) { return String(value || "") }
    function wireApiOptions() { return [{ "value": "responses", "text": "Responses API" }] }
    function wireApiLabel(value) { return String(value || "") }
    function wireApiValueFor(value) { return "responses" }
    function stableContextPreset() {
        return { "contextWindow": 400000, "autoCompactLimit": 320000,
                 "toolOutputLimit": 6000, "menuText": "稳定上下文" }
    }
    function millionContextPreset() {
        return { "contextWindow": 1000000, "autoCompactLimit": 800000,
                 "toolOutputLimit": 6000, "menuText": "百万上下文" }
    }
    function reasoningOptionsForModel(model) {
        return [{ "value": "high", "text": "高" }]
    }
    function highestReasoningEffortForModel(model) { return "high" }
    function contextPresetForModel(model) { return ({}) }
}
"""


def settle(milliseconds=600):
    """真实推进事件循环，让 QML 布局和 Expander 展开动画走完。"""
    deadline = time.monotonic() + milliseconds / 1000.0
    while time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.005)


class SectionLayoutTests(unittest.TestCase):
    def setUp(self):
        self._kept = []

    def _create(self, relative_path, *, width=1100, height=1400, properties=None):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        engine.addImportPath(str(VIEWS_DIR))
        stub = QQmlComponent(engine)
        stub.setData(STUB.encode("utf-8"), QUrl("inline:/stub.qml"))
        while not stub.isReady():
            APP.processEvents()
        stub_object = stub.create()
        self.assertIsNotNone(stub_object)
        engine.rootContext().setContextProperty("CodexConfig", stub_object)

        component = QQmlComponent(
            engine, QUrl.fromLocalFile(str(VIEWS_DIR / relative_path))
        )
        self.assertFalse(
            component.isError(),
            f"{relative_path} 加载失败: "
            + "; ".join(e.toString() for e in component.errors()),
        )
        root = component.create()
        self.assertIsNotNone(root)

        window = QQuickWindow()
        window.resize(width, height)
        root.setParentItem(window.contentItem())
        root.setProperty("width", width)
        root.setProperty("expanded", True)
        for name, value in (properties or {}).items():
            root.setProperty(name, value)
        window.show()
        settle()
        self._kept.extend([engine, stub, stub_object, component, root, window])
        return root, window

    def _assert_content_fits(self, root, relative_path):
        """展开后内容区必须包住全部可见子项，不能把底部裁掉。"""
        content_area = root.findChild(QQuickItem, "contentArea")
        self.assertIsNotNone(content_area, f"{relative_path} 找不到 contentArea")
        self.assertGreater(
            content_area.height(), 40, f"{relative_path} 展开后内容高度塌陷"
        )
        real_column = content_area.childItems()[0]
        self.assertAlmostEqual(
            content_area.height(),
            real_column.implicitHeight(),
            2.0,
            f"{relative_path} 内容区高度未跟随内部 implicitHeight（底部会被裁）",
        )
        return content_area

    def _find(self, root, object_name, relative_path):
        item = root.findChild(QQuickItem, object_name)
        self.assertIsNotNone(item, f"{relative_path} 缺少 {object_name}")
        self.assertGreater(item.width(), 100, f"{object_name} 宽度塌陷")
        self.assertGreater(item.height(), 20, f"{object_name} 高度塌陷")
        return item

    def test_connection_section_content_is_not_clipped(self):
        root, _ = self._create("ConnectionSection.qml")
        self._assert_content_fits(root, "ConnectionSection.qml")
        self._find(root, "baseUrlEdit", "ConnectionSection.qml")
        self._find(root, "providerEdit", "ConnectionSection.qml")
        self._find(root, "wireApiComboBox", "ConnectionSection.qml")
        self._find(root, "codexCredentialTabs", "ConnectionSection.qml")
        self._find(root, "codexApiKeyEdit", "ConnectionSection.qml")
        self._find(root, "authJsonInput", "ConnectionSection.qml")
        # 维护按钮已移进外抽屉，改由 test_toolbox_drawer_fits 覆盖。

    def test_toolbox_drawer_content_is_not_clipped(self):
        """抽屉是覆盖式 OverlayDialogCore（没有 contentArea/implicitHeight），
        因此校验真实面板尺寸与模式，而不是套用 Expander 的高度断言。"""
        root, window = self._create("ToolboxDrawer.qml")
        self.assertGreater(root.property("drawerWidth"), 0, "抽屉宽度未设置")
        self.assertGreater(root.property("drawerHeight"), 0, "抽屉高度未设置")
        self.assertEqual(
            root.property("mode"), 1, "工具抽屉必须用外抽屉（mode_outside）"
        )
        # 覆盖层填满宿主窗口，面板几何必须非零，否则内容会被裁成 0。
        self.assertGreater(root.width(), 0, "抽屉宽度塌陷")
        self.assertGreater(root.height(), 0, "抽屉高度塌陷")

    def test_toolbox_auto_opens_on_startup(self):
        """工具箱启动即展开，且只自动展开一次（用户收起后不弹回）。"""
        root, window = self._create("ToolboxDrawer.qml")

        def wait_opened(expected, timeout=3.0):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if bool(root.property("opened")) is expected:
                    settle(60)
                    return True
                APP.processEvents()
                time.sleep(0.005)
            return bool(root.property("opened")) is expected

        # 直接看最终结果 opened，而不是中间标志 autoOpened：只看标志会在
        # “标记了但没真打开”时假通过。
        self.assertTrue(wait_opened(True), "工具箱应在启动后自动展开")

        # 用户手动收起后，不能被自动展开逻辑再弹回来。
        root.close()
        self.assertTrue(wait_opened(False), "手动收起后应保持关闭")
        settle(400)
        self.assertFalse(
            root.property("opened"), "手动收起后不应被自动展开逻辑弹回"
        )

    def test_toolbox_content_fits_inside_drawer_padding(self):
        """内容必须交给 Drawer 的 contentItem 管理宽度。

        防回流：曾在外层再套一个 `width: root.drawerWidth` 的 Item，导致内容区
        被多减一次边距、右侧「执行」按钮被裁出面板。

        这里用结构约束而不是运行时测量：外抽屉的内容运行在独立窗口里，
        挂在普通窗口下实例化时量不到真实面板宽度，运行时断言会假通过。
        """
        source = (VIEWS_DIR / "ToolboxDrawer.qml").read_text(encoding="utf-8")

        # 根内容必须 anchors.fill: parent（填满 Drawer 已带边距的 contentItem）。
        self.assertIn("anchors.fill: parent", source)
        # 不得再按 drawerWidth 给内容定宽——那正是裁掉右边按钮的写法。
        self.assertNotIn(
            "width: root.drawerWidth",
            source,
            "ToolboxDrawer 的内容不应再按 drawerWidth 定宽（会多算一次边距）",
        )

    def test_address_fields_live_on_the_api_key_tab(self):
        """API 地址/提供商/协议属于「API 密钥」那一页，不能留在分段控件外面。"""
        root, _ = self._create("ConnectionSection.qml")
        tabs = root.findChild(QQuickItem, "codexCredentialTabs")
        self.assertIsNotNone(tabs, "缺少分段控件")

        for name in ("baseUrlEdit", "providerEdit", "wireApiComboBox"):
            item = root.findChild(QQuickItem, name)
            self.assertIsNotNone(item, f"缺少 {name}")
            self.assertTrue(
                item.isVisible(),
                f"{name} 在默认的 API 密钥页应当可见",
            )

        # 切到 JSON 页后，连接信息整块让位。
        tabs.setProperty("currentIndex", 1)
        settle(300)
        for name in ("baseUrlEdit", "providerEdit", "wireApiComboBox"):
            item = root.findChild(QQuickItem, name)
            self.assertFalse(
                item.isVisible(),
                f"{name} 在 ChatGPT JSON 页不应出现",
            )
        self.assertTrue(
            root.findChild(QQuickItem, "authJsonInput").isVisible(),
            "JSON 页应显示导入框",
        )

    def test_model_section_content_is_not_clipped(self):
        root, _ = self._create("ModelSection.qml")
        self._assert_content_fits(root, "ModelSection.qml")
        self._find(root, "modelEdit", "ModelSection.qml")

    def test_model_fields_stack_vertically_with_full_width(self):
        """字段按「标题 → 说明 → 控件」单列纵向堆叠，每个字段占满整行宽度。

        防回流：曾经并排两列，带说明的字段比兄弟高一截，GridLayout 会把矮的
        那个垂直居中，两边控件顶部错开；说明文字也曾排在控件下方。
        """
        root, _ = self._create("ModelSection.qml")
        container = root.findChild(QQuickItem, "modelGrid")
        self.assertIsNotNone(container, "找不到 modelGrid")
        self.assertIsNone(
            container.property("columns"),
            "modelGrid 不应再是 GridLayout（单列纵向堆叠即可）",
        )

        fields = [
            c for c in container.childItems() if c.property("label") is not None
        ]
        self.assertEqual(len(fields), 2, "模型区应有「当前模型 / 在线模型列表」两个字段")

        previous_bottom = None
        for field in fields:
            self.assertAlmostEqual(
                field.width(),
                container.width(),
                2.0,
                f"{field.property('label')} 应占满整行宽度",
            )
            column = field.childItems()[0]
            parts = column.childItems()
            self.assertEqual(
                len(parts), 3, f"{field.property('label')} 应恰好三行：标题/说明/控件"
            )
            title_row, caption, host = parts
            # 没有说明文字时该行折叠为 0 高并收在顶部，此时只校验控件在标题下。
            if caption.isVisible() and caption.height() > 0:
                self.assertLess(
                    title_row.y() + title_row.height(),
                    caption.y() + 0.5,
                    "说明文字必须排在标题下方",
                )
                self.assertLess(
                    caption.y() + caption.height(),
                    host.y() + 0.5,
                    "控件必须排在说明文字下方",
                )
            else:
                self.assertLess(
                    title_row.y() + title_row.height(),
                    host.y() + 0.5,
                    "控件必须排在标题下方",
                )
            if previous_bottom is not None:
                self.assertGreaterEqual(
                    field.y() + 0.5,
                    previous_bottom,
                    "字段之间不得重叠，应自上而下依次堆叠",
                )
            previous_bottom = field.y() + field.height()

        # 思考等级也必须并进同一套 FormField 尺寸，不能自己封顶一个窄下拉。
        effort = root.findChild(QQuickItem, "effortBox")
        self.assertIsNotNone(effort, "找不到思考等级下拉")
        self.assertAlmostEqual(
            effort.width(), container.width(), 2.0,
            "思考等级下拉应与其它字段等宽（不再写死 280 封顶）",
        )

    def test_form_fields_share_one_column_across_sections(self):
        """各节字段一律单列：GridLayout 里不该再给 FormField 定两列宽度。"""
        for name in (
            "ConnectionSection.qml",
            "ContextSection.qml",
            "ClaudeGatewaySection.qml",
            "ClaudeAdvancedSection.qml",
        ):
            source = (VIEWS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "equalItemWidth",
                source,
                f"{name} 仍在按等分宽度并排字段，应改为单列纵向堆叠",
            )
            self.assertIn("ColumnLayout", source, f"{name} 应改用单列 ColumnLayout")


    def test_context_section_content_is_not_clipped(self):
        root, _ = self._create("ContextSection.qml")
        self._assert_content_fits(root, "ContextSection.qml")
        for object_name in (
            "contextWindowEdit",
            "autoCompactEdit",
            "toolOutputEdit",
        ):
            self._find(root, object_name, "ContextSection.qml")

    def test_advanced_section_content_is_not_clipped(self):
        root, _ = self._create("AdvancedSection.qml")
        self._assert_content_fits(root, "AdvancedSection.qml")
        self._find(root, "requiresAuthToggle", "AdvancedSection.qml")

    def test_claude_gateway_section_content_is_not_clipped(self):
        root, _ = self._create("ClaudeGatewaySection.qml")
        self._assert_content_fits(root, "ClaudeGatewaySection.qml")
        self._find(root, "claudeEndpointEdit", "ClaudeGatewaySection.qml")
        self._find(root, "claudeApiKeyEdit", "ClaudeGatewaySection.qml")


if __name__ == "__main__":
    unittest.main()
