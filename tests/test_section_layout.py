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
        self._find(root, "repairRelayAuthButton", "ConnectionSection.qml")
        self._find(root, "sandboxStopgapButton", "ConnectionSection.qml")
        self._find(root, "authJsonInput", "ConnectionSection.qml")

    def test_model_section_content_is_not_clipped(self):
        root, _ = self._create("ModelSection.qml")
        self._assert_content_fits(root, "ModelSection.qml")
        self._find(root, "modelEdit", "ModelSection.qml")

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
