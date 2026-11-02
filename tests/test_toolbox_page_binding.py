# coding: utf-8
"""工具箱只跟随 Codex 页显隐（真行为门禁）。

历史背景（真实 BUG）：工具箱曾是外抽屉（mode_outside），宿主窗口之外另开一个
HWND。页面栈切页只把页面 Item 的 visible 置假，外抽屉的独立窗口不受影响，
于是切到 Claude / 设置页后，Codex 的维护工具箱仍然挂在主窗口外面。

现在工具箱是内抽屉（mode_inside），挂在 Codex 页容器内部，天然跟随本页显隐；
但「页面失活就收起、回到本页再恢复」的行为仍保留，避免残留展开态或遮罩。
这些用例继续锁住该行为，防止被改回“自己测自己”的空壳。

这里不放源码字符串断言：把 ToolboxDrawer 真实例化进一个真实窗口的页面容器，
用真实的 open/close 走完整个链路，再核对 opened 状态。
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


def settle(milliseconds=600):
    deadline = time.monotonic() + milliseconds / 1000.0
    while time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.005)


def wait_opened(root, expected, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if bool(root.property("opened")) is expected:
            settle(80)
            return True
        APP.processEvents()
        time.sleep(0.005)
    return bool(root.property("opened")) is expected


class ToolboxPageBindingTests(unittest.TestCase):
    def setUp(self):
        self._kept = []

    def _create(self, *, page_active=True, width=1100, height=800):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        engine.addImportPath(str(VIEWS_DIR))
        component = QQmlComponent(
            engine, QUrl.fromLocalFile(str(VIEWS_DIR / "ToolboxDrawer.qml"))
        )
        self.assertFalse(
            component.isError(),
            "ToolboxDrawer.qml 加载失败: "
            + "; ".join(e.toString() for e in component.errors()),
        )

        window = QQuickWindow()
        window.resize(width, height)

        # 内抽屉的真实用法：抽屉的覆盖宿主是一个页面级容器，而不是窗口内容项。
        # 这里照搬 CodexView 的接线（overlayHost: 页面 Item），否则抽屉没有宿主、
        # 不会自动展开，测的就不是真实链路。
        page = QQuickItem(window.contentItem())
        page.setWidth(width)
        page.setHeight(height)
        window.contentItem().setProperty("pageHost", page)

        root = component.create()
        self.assertIsNotNone(root)
        root.setParentItem(page)
        root.setProperty("overlayHost", page)
        root.setProperty("width", width)
        root.setProperty("height", height)
        root.setProperty("pageActive", page_active)
        window.show()
        settle()
        self._kept.extend([engine, component, root, window, page])
        return root, window

    def test_drawer_closes_when_page_goes_inactive(self):
        """离开 Codex 页必须收起：否则那只属于 Codex 的抽屉会留在别的页外面。"""
        root, _ = self._create()
        self.assertTrue(wait_opened(root, True), "Codex 页上工具箱应自动展开")

        root.setProperty("pageActive", False)
        self.assertTrue(
            wait_opened(root, False),
            "页面失活后工具箱必须收起，不能在 Claude/设置页外面继续显示",
        )

    def test_drawer_returns_when_page_comes_back(self):
        """回到 Codex 页要恢复展开，但只恢复“离开时本来就展开”的那次。"""
        root, _ = self._create()
        self.assertTrue(wait_opened(root, True))

        root.setProperty("pageActive", False)
        self.assertTrue(wait_opened(root, False))

        root.setProperty("pageActive", True)
        self.assertTrue(
            wait_opened(root, True),
            "回到 Codex 页时，离开前展开的工具箱应当恢复展开",
        )

    def test_manually_closed_drawer_never_pops_back_after_page_return(self):
        """用户手动收起过，就不能借“切页回来”把抽屉弹回来。"""
        root, _ = self._create()
        self.assertTrue(wait_opened(root, True))

        root.close()
        self.assertTrue(wait_opened(root, False), "手动收起后应保持关闭")

        root.setProperty("pageActive", False)
        settle(200)
        root.setProperty("pageActive", True)
        settle(400)
        self.assertFalse(
            bool(root.property("opened")),
            "用户手动收起的工具箱不应在切页返回时自动弹回",
        )

    def test_inactive_page_never_auto_opens(self):
        """页面从一创建就是失活态时，自动展开逻辑不许抢跑开抽屉。"""
        root, _ = self._create(page_active=False)
        settle(500)
        self.assertFalse(
            bool(root.property("opened")),
            "失活页面（非 Codex 页）不应自动弹出工具箱",
        )

        root.setProperty("pageActive", True)
        self.assertTrue(
            wait_opened(root, True),
            "首次进入 Codex 页时工具箱应当自动展开",
        )


class CodexPageToolboxTests(unittest.TestCase):
    """把真实的 CodexView 例化出来，验证「切页 → 抽屉跟着走」这条完整链路。

    只断言 ToolboxDrawer 自己的行为不够：漏掉 CodexView 里那行
    `pageActive: root.pageActive` 接线，抽屉依然「自己测自己」全绿，而线上
    依旧会在 Claude 页外面挂着工具箱。所以这里必须从页面这一层验。
    """

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
    property var availableModels: []
    property string subagentModel: ""
    property string subagentReasoningEffort: ""

    function normalizedBaseUrl(value) { return String(value || "") }
    function wireApiOptions() { return [{ "value": "responses", "text": "Responses API" }] }
    function wireApiLabel(value) { return String(value || "") }
    function wireApiValueFor(value) { return "responses" }
    function stableContextPreset() { return ({}) }
    function millionContextPreset() { return ({}) }
    function reasoningOptionsForModel(model) { return [] }
    function highestReasoningEffortForModel(model) { return "high" }
    function contextPresetForModel(model) { return ({}) }
}
"""

    def setUp(self):
        self._kept = []

    def _create(self):
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        engine.addImportPath(str(VIEWS_DIR))
        stub = QQmlComponent(engine)
        stub.setData(self.STUB.encode("utf-8"), QUrl("inline:/stub.qml"))
        while not stub.isReady():
            APP.processEvents()
        stub_object = stub.create()
        self.assertIsNotNone(stub_object)
        engine.rootContext().setContextProperty("CodexConfig", stub_object)

        component = QQmlComponent(
            engine, QUrl.fromLocalFile(str(VIEWS_DIR / "CodexView.qml"))
        )
        self.assertFalse(
            component.isError(),
            "CodexView.qml 加载失败: "
            + "; ".join(e.toString() for e in component.errors()),
        )
        root = component.create()
        self.assertIsNotNone(root)

        window = QQuickWindow()
        window.resize(1100, 800)
        root.setParentItem(window.contentItem())
        root.setProperty("width", 1100)
        root.setProperty("height", 800)
        window.show()
        settle()
        self._kept.extend([engine, stub, stub_object, component, root, window])
        return root, window

    def _drawer(self, root):
        drawer = root.findChild(QQuickItem, "codexToolboxDrawer")
        self.assertIsNotNone(drawer, "CodexView 里找不到工具箱抽屉")
        return drawer

    def test_toolbox_follows_codex_page_visibility(self):
        """页面可见性一变，抽屉必须跟着变——这一条才真正覆盖接线。"""
        root, window = self._create()
        drawer = self._drawer(root)
        self.assertTrue(wait_opened(drawer, True), "Codex 页上工具箱应自动展开")

        # 页面栈切走时就是把页面 Item 的 visible 置假。
        root.setProperty("visible", False)
        self.assertTrue(
            wait_opened(drawer, False),
            "Codex 页隐藏后工具箱必须收起（切到 Claude/设置页时不能残留）",
        )

        root.setProperty("visible", True)
        self.assertTrue(
            wait_opened(drawer, True),
            "回到 Codex 页后，离开前展开的工具箱应恢复展开",
        )


class ToolboxPageWiringTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_toolbox_declares_activity_props(self):
        toolbox = self.read("qml/views/ToolboxDrawer.qml")
        self.assertIn("property bool pageActive: true", toolbox)
        self.assertIn("function closeForInactivePage()", toolbox)
        self.assertIn("function restoreForActivePage()", toolbox)
        self.assertIn("onPageActiveChanged", toolbox)


if __name__ == "__main__":
    unittest.main()
