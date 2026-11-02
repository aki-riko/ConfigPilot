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
from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIEWS_DIR = ROOT / "qml" / "views"

from tests.qt_test_utils import APP  # noqa: E402


# 读取真实 zIndex 层级，供底部栏层级门禁使用。
_ZINDEX_SCENE = """
import QtQuick
import PrismQML as Fluent

QtObject {
    readonly property var layers: ({
        "background": Fluent.Enums.zIndex.background,
        "content": Fluent.Enums.zIndex.content,
        "controls": Fluent.Enums.zIndex.controls,
        "modal": Fluent.Enums.zIndex.modal,
        "overlay": Fluent.Enums.zIndex.overlay
    })
}
"""


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

    def _create(self, relative_path, *, width=1100, height=1400, properties=None,
                with_overlay_host=False):
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
        # 内抽屉需要显式的覆盖宿主（页面级容器）。真实调用方（CodexView）就是这么
        # 接的；不传就退回窗口内容项，测到的不是内抽屉的真实链路。
        page_host = None
        if with_overlay_host:
            page_host = QQuickItem(window.contentItem())
            page_host.setWidth(width)
            page_host.setHeight(height)
            root.setParentItem(page_host)
            root.setProperty("overlayHost", page_host)
        root.setProperty("width", width)
        root.setProperty("expanded", True)
        for name, value in (properties or {}).items():
            root.setProperty(name, value)
        window.show()
        settle()
        kept = [engine, stub, stub_object, component, root, window]
        if page_host is not None:
            kept.append(page_host)
        self._kept.extend(kept)
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
        root, window = self._create("ToolboxDrawer.qml", with_overlay_host=True)
        self.assertGreater(root.property("drawerWidth"), 0, "抽屉宽度未设置")
        self.assertGreater(root.property("drawerHeight"), 0, "抽屉高度未设置")
        # 内抽屉（mode_inside = 0）：在本页容器内滑出，遮罩只覆盖本页。
        # 防回流：曾用外抽屉（mode_outside = 1），它是宿主窗口外的独立 HWND，
        # 切页不会跟随，必须额外写「页面失活就收起」的补丁才能不残留。
        self.assertEqual(
            root.property("mode"), 0, "工具抽屉必须用内抽屉（mode_inside）"
        )
        # 覆盖层填满宿主窗口，面板几何必须非零，否则内容会被裁成 0。
        self.assertGreater(root.width(), 0, "抽屉宽度塌陷")
        self.assertGreater(root.height(), 0, "抽屉高度塌陷")

    def test_toolbox_auto_opens_on_startup(self):
        """工具箱启动即展开，且只自动展开一次（用户收起后不弹回）。"""
        root, window = self._create("ToolboxDrawer.qml", with_overlay_host=True)

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

        这里用结构约束而不是运行时测量：面板宽度由 Drawer 内部按 drawerWidth
        与父级几何共同决定，挂在测试窗口下实例化时未必等于真实运行宽度，
        运行时断言容易假通过。
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

    def test_action_bars_stay_below_the_overlay_layer(self):
        """底部操作栏必须低于覆盖层，抽屉/遮罩打开时整页一起变暗。

        真实缺陷：两个页面的底部栏都写死 `z: 10`，而 PrismQML 的覆盖层用
        zIndex.modal(=6)。结果工具箱内抽屉打开后，页面内容变暗、底部栏却照常
        明亮地浮在遮罩之上，出现明显割裂。

        这里实例化真实页面并读取底部栏的实际 z 值，而不是只校验枚举关系——
        后者抓不到「页面退回写死 10」这类回退。
        """
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        engine.addImportPath(str(VIEWS_DIR))
        stub_comp = QQmlComponent(engine)
        stub_comp.setData(STUB.encode("utf-8"), QUrl("inline:/stub.qml"))
        while not stub_comp.isReady():
            APP.processEvents()
        stub = stub_comp.create()
        self.assertIsNotNone(stub)
        engine.rootContext().setContextProperty("CodexConfig", stub)

        modal_z = self._overlay_layer_z()
        self.assertGreater(modal_z, 1, "覆盖层必须高于内容层")

        try:
            for view_name, bar_name in (
                ("CodexView.qml", "codexActionBar"),
                ("ClaudeDesktopView.qml", "claudeActionBar"),
            ):
                component = QQmlComponent(
                    engine, QUrl.fromLocalFile(str(VIEWS_DIR / view_name))
                )
                self.assertFalse(
                    component.isError(),
                    f"{view_name} 加载失败: "
                    + "; ".join(e.toString() for e in component.errors()),
                )
                root = component.create()
                self.assertIsNotNone(root)
                window = QQuickWindow()
                window.resize(1000, 760)
                root.setParentItem(window.contentItem())
                root.setProperty("width", 1000)
                root.setProperty("height", 760)
                window.show()
                settle(120)
                try:
                    bar = root.findChild(QQuickItem, bar_name)
                    self.assertIsNotNone(
                        bar, f"{view_name} 里找不到底部栏 {bar_name}"
                    )
                    self.assertLess(
                        bar.z(),
                        modal_z,
                        f"{view_name} 的底部栏 z={bar.z()} 不低于覆盖层 "
                        f"z={modal_z}，抽屉打开时会浮在遮罩之上",
                    )
                    self.assertGreater(
                        bar.z(),
                        1,
                        f"{view_name} 的底部栏 z={bar.z()} 过低，会被内容盖住",
                    )
                finally:
                    window.close()
                    window.deleteLater()
                    component.deleteLater()
                    QCoreApplication.sendPostedEvents(
                        None, QEvent.Type.DeferredDelete
                    )
                    APP.processEvents()
        finally:
            stub.deleteLater()
            stub_comp.deleteLater()
            engine.deleteLater()
            APP.processEvents()

    def _overlay_layer_z(self):
        """读取 PrismQML 覆盖层(modal)的真实 z 值。"""
        engine = QQmlEngine()
        engine.addImportPath(os.path.dirname(prismqml.__file__))
        try:
            comp = QQmlComponent(engine)
            comp.setData(
                _ZINDEX_SCENE.encode("utf-8"),
                QUrl("inline:/zindex-scene.qml"),
            )
            while comp.status() == QQmlComponent.Status.Loading:
                APP.processEvents()
            self.assertFalse(
                comp.isError(),
                "层级场景加载失败: "
                + "; ".join(e.toString() for e in comp.errors()),
            )
            obj = comp.create()
            self.assertIsNotNone(obj)
            try:
                layers = obj.property("layers")
                resolved = (
                    layers.toVariant() if hasattr(layers, "toVariant") else layers
                )
                return resolved["modal"]
            finally:
                obj.deleteLater()
                comp.deleteLater()
                QCoreApplication.sendPostedEvents(
                    None, QEvent.Type.DeferredDelete
                )
                APP.processEvents()
        finally:
            engine.deleteLater()
            APP.processEvents()

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

    def test_model_fields_are_inline_label_left_control_right(self):
        """字段按「左侧标题+说明 / 右侧控件」内联排布，每个字段占满整行宽度。

        防回流历史：更早是并排两列（带说明的字段比兄弟高一截，GridLayout 会把
        矮的那个垂直居中，两边控件顶部错开）；后来改成「标题 → 说明 → 控件」
        三行纵向堆叠，单字段固定吃掉 50~66px，一屏放不下几个字段。现在的约定
        是标签内联：字段仍各占一整行，但内部左右两栏，单字段高度收敛到控件高度。
        """
        root, _ = self._create("ModelSection.qml")
        container = root.findChild(QQuickItem, "modelGrid")
        self.assertIsNotNone(container, "找不到 modelGrid")
        self.assertIsNone(
            container.property("columns"),
            "modelGrid 不应再是 GridLayout（字段各占一行，左右分栏在字段内部）",
        )

        fields = [
            c for c in container.childItems() if c.property("label") is not None
        ]
        self.assertEqual(len(fields), 2, "模型区应有「当前模型 / 在线模型列表」两个字段")

        previous_bottom = None
        for field in fields:
            label = field.property("label")
            self.assertAlmostEqual(
                field.width(),
                container.width(),
                2.0,
                f"{label} 应占满整行宽度",
            )
            row = field.childItems()[0]
            parts = row.childItems()
            self.assertEqual(len(parts), 2, f"{label} 应恰好两栏：左侧标签 / 右侧控件")
            label_column, host = parts

            # 标签在左、控件在右，且两栏顶部对齐（控件不能被垂直居中挤下去）。
            self.assertLess(
                label_column.x() + label_column.width(),
                host.x() + 0.5,
                f"{label} 的标签列必须在控件左侧",
            )
            self.assertAlmostEqual(
                label_column.y(),
                host.y(),
                2.0,
                f"{label} 的标签列与控件必须顶部对齐",
            )

            # 标签列内部仍是「标题行 → 说明行」，控件宿主不得小于控件本体高度。
            title_row, caption = label_column.childItems()
            if caption.isVisible() and caption.height() > 0:
                self.assertLess(
                    title_row.y() + title_row.height(),
                    caption.y() + 0.5,
                    f"{label} 的说明文字必须排在标题下方",
                )
            self.assertGreater(
                host.width(),
                label_column.width(),
                f"{label} 的控件区应比标签列宽（标签不抢占控件空间）",
            )
            self.assertGreater(
                host.height(),
                20,
                f"{label} 的控件宿主高度塌陷",
            )

            if previous_bottom is not None:
                self.assertGreaterEqual(
                    field.y() + 0.5,
                    previous_bottom,
                    "字段之间不得重叠，应自上而下依次堆叠",
                )
            previous_bottom = field.y() + field.height()

        # 思考等级也必须并进同一套 FormField 尺寸，不能自己封顶一个窄下拉。
        # 标签内联后控件区不再等于整行宽度，而是与其它字段的控件区一致。
        effort = root.findChild(QQuickItem, "effortBox")
        self.assertIsNotNone(effort, "找不到思考等级下拉")
        other_host = fields[0].childItems()[0].childItems()[1]
        self.assertAlmostEqual(
            effort.width(), other_host.width(), 2,
            "思考等级下拉应与其它字段的控件区等宽（不再写死 280 封顶）",
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

    def test_context_preset_dropdown_lives_in_header_and_drives_actions(self):
        """三个预设动作收进头部下拉：菜单项按可用性出现，点击要真的发出信号。

        防回流两层：
        1. 下拉按钮必须在展开器头部，不能回到内容区横铺三个按钮（会常驻
           占掉内容区一整行，实测内容区高度从 170 涨回 214）。
        2. 菜单项的文字分发必须真的连到 presetRequested / millionPresetRequested
           / clearRequested ——拼对菜单文字但点下去没反应是最容易漏的坑。
        """
        root, _ = self._create("ContextSection.qml")
        button = root.findChild(QQuickItem, "contextPresetDropdown")
        self.assertIsNotNone(button, "找不到上下文预设下拉按钮")

        content_area = root.findChild(QQuickItem, "contentArea")
        self.assertIsNotNone(content_area, "找不到 contentArea")
        # 按钮不能在内容区里（否则就是又回到横铺占用内容高度）。
        self.assertFalse(
            self._is_descendant_of(button, content_area),
            "预设下拉必须留在展开器头部，不能塞回内容区",
        )
        self.assertTrue(button.isVisible(), "预设下拉应当可见")

        # 两个预设都可用时，菜单项齐全（含分隔线）。
        root.setProperty("currentPreset", {
            "contextWindow": 400000, "autoCompactLimit": 320000,
            "toolOutputLimit": 6000, "menuText": "稳定上下文",
        })
        root.setProperty("millionPreset", {
            "contextWindow": 1000000, "autoCompactLimit": 800000,
            "toolOutputLimit": 6000, "menuText": "百万上下文",
        })
        settle(300)
        texts = self._menu_texts(button)
        self.assertEqual(
            texts,
            ["套用稳定上下文", "套用百万上下文", "-", "清空自定义值"],
            "预设齐全时菜单项不对",
        )

        # 每个菜单项的图标必须能区分用途：两个预设曾经都是勾号，菜单里长得
        # 一模一样，用户分不出套用哪个。要求三项图标互不相同，且真的解析出
        # 了图标路径（空字符串等于没图标）。
        icons = self._menu_icon_paths(button)
        self.assertEqual(len(icons), 4, "菜单项数量与图标数量不一致")
        for index, path in enumerate(icons):
            if texts[index] == "-":
                continue
            self.assertTrue(
                path, f"菜单项「{texts[index]}」没有图标"
            )
        preset_icons = {icons[0], icons[1]}
        self.assertEqual(
            len(preset_icons), 2,
            "两个预设的图标必须不同，否则菜单里分不出套用哪个",
        )
        self.assertNotIn(
            icons[2], preset_icons,
            "「清空自定义值」的图标不能和预设项重复",
        )

        # 百万预设不可用时，该项必须整条消失（内置菜单不支持单项置灰）。
        root.setProperty("millionPreset", {})
        settle(300)
        self.assertEqual(
            self._menu_texts(button),
            ["套用稳定上下文", "-", "清空自定义值"],
            "不可用的百万预设应整条不出现",
        )

        # 点了要真的发出对应信号。
        fired = []
        root.presetRequested.connect(lambda: fired.append("preset"))
        root.millionPresetRequested.connect(lambda: fired.append("million"))
        root.clearRequested.connect(lambda: fired.append("clear"))
        for index, text, expected in (
            (0, "套用稳定上下文", "preset"),
            (2, "清空自定义值", "clear"),
        ):
            fired.clear()
            button.menuItemClicked.emit(index, text)
            settle(120)
            self.assertIn(expected, fired, f"点「{text}」未触发 {expected}")

    @staticmethod
    def _menu_texts(button):
        items = button.property("menuItems")
        converted = items.toVariant() if hasattr(items, "toVariant") else items
        texts = []
        for item in converted or []:
            texts.append(item.get("text") if isinstance(item, dict) else str(item))
        return texts

    @staticmethod
    def _menu_icon_paths(button):
        """取每个菜单项的图标资源路径（解析后），分隔线为空字符串。"""
        items = button.property("menuItems")
        converted = items.toVariant() if hasattr(items, "toVariant") else items
        paths = []
        for item in converted or []:
            if not isinstance(item, dict):
                paths.append("")
                continue
            text = item.get("text")
            if text == "-":
                paths.append("")
                continue
            icon = item.get("icon") or ""
            paths.append(str(icon))
        return paths

    @staticmethod
    def _is_descendant_of(item, ancestor):
        node = item
        while node is not None:
            if node is ancestor:
                return True
            node = node.parentItem()
        return False

    def test_advanced_section_content_is_not_clipped(self):
        root, _ = self._create("AdvancedSection.qml")
        self._assert_content_fits(root, "AdvancedSection.qml")
        self._find(root, "requiresAuthToggle", "AdvancedSection.qml")

    def test_claude_gateway_section_content_is_not_clipped(self):
        root, _ = self._create("ClaudeGatewaySection.qml")
        self._assert_content_fits(root, "ClaudeGatewaySection.qml")
        self._find(root, "claudeEndpointEdit", "ClaudeGatewaySection.qml")
        self._find(root, "claudeApiKeyEdit", "ClaudeGatewaySection.qml")

    def test_claude_status_items_never_overflow_the_available_width(self):
        """三个状态项并排后，任何宽度下都不得把第三项挤出右边界或压成 0 宽。

        防回流：曾用 RowLayout 横排，窄窗口不折行，实测 760px 下三个子项
        需要 632px 而只分到 508px，第三项直接被裁掉；改用 Flow 也不行——
        Flow 是 positioner，不读子项的 Layout.preferredWidth，会按
        implicitWidth 各自乱排。必须是按宽度折列的 GridLayout。

        注意：只断言「不溢出」不够——把 GridLayout 写死 3 列时，格子会被
        压窄但不会越界，断言照样通过。所以这里同时要求窄窗口必须折行
        （出现第二行），这才是折列真正生效的证据。
        """
        for width in (1100, 900, 760):
            root, _ = self._create(
                "ClaudeStatusSection.qml", width=width, height=1200
            )
            status_grid = root.findChild(QQuickItem, "statusGrid")
            self.assertIsNotNone(status_grid, "找不到 statusGrid")
            # statusGrid 是外层 ColumnLayout，真正排三个状态格的是它里面的
            # GridLayout（childItems 第一个）。
            cells_parent = status_grid.childItems()[0]
            cells = cells_parent.childItems()
            self.assertEqual(len(cells), 3, f"{width}px 下状态格数量异常")

            widest_right = 0.0
            available = cells_parent.width()
            for cell in cells:
                for item in cell.childItems():
                    widest_right = max(widest_right, item.x() + item.width())
            self.assertLessEqual(
                widest_right,
                available + 1.0,
                f"{width}px 下状态项溢出：最右 {widest_right:.1f} > 可用 {available:.1f}",
            )
            self.assertGreater(
                available, 100, f"{width}px 下状态区宽度塌陷"
            )
            # 每个格子都得有可用宽度：被压成几十像素等于用不了。
            thinnest = min(cell.width() for cell in cells)
            self.assertGreater(
                thinnest,
                120,
                f"{width}px 下最窄状态格只有 {thinnest:.1f}px，内容会被压扁",
            )
            for name in ("claudeDeveloperModeToggle", "claudeGatewayToggle"):
                toggle = root.findChild(QQuickItem, name)
                self.assertIsNotNone(toggle, f"找不到 {name}")
                self.assertGreater(
                    toggle.width(), 100, f"{width}px 下 {name} 宽度塌陷"
                )

        # 窄窗口必须真的折行：宽窗口一行放得下三格，760px 不该还挤成一行。
        narrow, _ = self._create(
            "ClaudeStatusSection.qml", width=760, height=1200
        )
        narrow_grid = narrow.findChild(QQuickItem, "statusGrid")
        narrow_cells = narrow_grid.childItems()[0].childItems()
        row_positions = {round(cell.y()) for cell in narrow_cells}
        self.assertGreater(
            len(row_positions), 1,
            "760px 下三个状态项仍挤在一行，折列没有生效",
        )


    def test_toolbox_subagent_picker_only_offers_fetched_models(self):
        """「修复降智」的模型下拉只能列出「获取模型」的真实结果。

        防回流背景：旧实现由代码内置 gpt-6-sol 一键写入，会把用户自己在 Codex
        侧调好的子代理配置覆盖掉。现在必须用户手动从「获取模型」的结果里选，
        因此这里对着真实实例化的抽屉断言：
        1. 没有列表时下拉不可用、执行按钮不可用；
        2. 拿到列表后下拉可用，且按 config.toml 里现有的模型预选；
        3. 手动改选后，执行信号必须带着用户选中的那个模型名；
        4. 列表刷新丢了已选模型时，选中态必须清空（不能拿旧值去写）。
        """
        root, _ = self._create(
            "ToolboxDrawer.qml",
            properties={
                "subagentModel": "gpt-6.1-sol",
                "subagentReasoningEffort": "max",
            },
        )
        box = root.findChild(QQuickItem, "subagentModelBox")
        fetch = root.findChild(QQuickItem, "subagentModelFetchButton")
        summary = root.findChild(QQuickItem, "subagentCurrentText")
        self.assertIsNotNone(box, "找不到模型下拉")
        self.assertIsNotNone(fetch, "找不到获取模型按钮")
        self.assertIsNotNone(summary, "找不到当前配置回显")
        self.assertIn("gpt-6.1-sol", summary.property("text"))

        # 1) 没有列表：下拉与执行都不可用。
        self.assertFalse(box.isEnabled(), "没有模型列表时下拉不应可用")
        self.assertEqual(root.property("selectedSubagentModel"), "")

        # 2) 拿到列表：下拉可用，并预选到 config.toml 里现有的模型。
        root.setProperty(
            "availableModels", ["gpt-6.1-sol", "gpt-5.6-sol", "gpt-5.5"]
        )
        settle(300)
        self.assertTrue(box.isEnabled(), "拿到列表后下拉应可用")
        self.assertEqual(
            root.property("selectedSubagentModel"),
            "gpt-6.1-sol",
            "应按当前配置预选子代理模型",
        )

        # 3) 手动改选后，执行信号带的是用户选中的模型。
        box.activated.emit(1)
        settle(120)
        self.assertEqual(root.property("selectedSubagentModel"), "gpt-5.6-sol")
        fired = []
        root.repairSubagentDefaultsRequested.connect(lambda m: fired.append(m))
        root.repairSubagentDefaultsRequested.emit(
            root.property("selectedSubagentModel")
        )
        settle(120)
        self.assertEqual(fired, ["gpt-5.6-sol"])

        # 4) 列表刷新丢了已选模型，选中态必须清空。
        root.setProperty("availableModels", ["gpt-5.5"])
        settle(300)
        self.assertEqual(
            root.property("selectedSubagentModel"),
            "",
            "已选模型不在新列表里时必须清空，避免拿旧值写配置",
        )


if __name__ == "__main__":
    unittest.main()
