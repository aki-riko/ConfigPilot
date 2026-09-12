# coding: utf-8
"""桌宠 QML 的真实加载测试。

静态文本断言抓不到"QML 语法/结构被改坏"这类问题(桌宠面板是嵌套层数最深的
QML 之一,曾经因为少一个大括号导致卡片内容被裁掉)。这里用替身数据把
PetWindow / PetPanel 真正实例化一次,并核对三种形态的窗口高度。
"""

import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PET_DIR = ROOT / "qml" / "pet"

from PySide6.QtCore import Property, QObject, QPoint, Qt, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


# 实例化 Window 需要 QGuiApplication(conftest.py 已保证平台与实例)
APP = QGuiApplication.instance()


def _collect(root, predicate, out):
    """递归收集 QQuickItem 子树中满足条件的节点。"""
    if predicate(root):
        out.append(root)
    for child in root.childItems():
        _collect(child, predicate, out)


class _QmlWarningCapture:
    """捕获 Qt 侧消息,用来断言交互过程中没有 QML 运行期警告。"""

    def __init__(self):
        self._messages = []
        self._previous = None

    def _handler(self, mode, context, message):
        self._messages.append(str(message))

    def __enter__(self):
        from PySide6.QtCore import qInstallMessageHandler

        self._previous = qInstallMessageHandler(self._handler)
        return self

    def __exit__(self, exc_type, exc, tb):
        from PySide6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(self._previous)
        return False

    def stop(self):
        if self._previous is not None:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(self._previous)
            self._previous = None
        # 有些 Qt 消息会带换行,拆开便于阅读
        return [line for message in self._messages for line in message.splitlines() if line.strip()]


def _capture_qml_warnings():
    return _QmlWarningCapture()


# 与 PetWindow.qml / PetPanel.qml 里的布局常量保持一致
PANEL_PADDING = 8
SPRITE_SIZE = 120
SPRITE_BOTTOM_MARGIN = PANEL_PADDING
SPRITE_GAP = PANEL_PADDING * 2
CARD_TOP = PANEL_PADDING
DETAIL_CONTENT_HEIGHT = 344
BUBBLE_HEIGHT = 76
BUBBLE_TOP = PANEL_PADDING
EXPECTED_HEIGHTS = {
    "detail": CARD_TOP + DETAIL_CONTENT_HEIGHT + SPRITE_GAP + SPRITE_SIZE + SPRITE_BOTTOM_MARGIN,
    "bubble": BUBBLE_TOP + BUBBLE_HEIGHT + SPRITE_GAP + SPRITE_SIZE + SPRITE_BOTTOM_MARGIN,
    "pet": SPRITE_BOTTOM_MARGIN + SPRITE_SIZE + SPRITE_GAP,
}
# pet 形态的高度,需要能完整放下桌宠(否则桌宠会被裁到窗口外)
PET_MODE_MIN_HEIGHT = SPRITE_BOTTOM_MARGIN + SPRITE_SIZE


class StubPet(QObject):
    """桌宠控制器的替身:提供 QML 需要的全部只读属性。"""

    usageChanged = Signal()
    logsChanged = Signal()
    statusChanged = Signal()
    configSaved = Signal()
    saveErrorChanged = Signal()
    usageBumped = Signal()
    sourcesChanged = Signal()
    accountChanged = Signal()

    @Property(bool, notify=statusChanged)
    def sourceReady(self): return True
    @Property(bool, notify=statusChanged)
    def hasError(self): return False
    @Property(bool, notify=usageChanged)
    def lowBalance(self): return False
    @Property(str, notify=usageChanged)
    def tokenName(self): return "Codex"
    @Property(str, notify=usageChanged)
    def balanceText(self): return "∞"
    @Property(str, notify=usageChanged)
    def grantedText(self): return "∞"
    @Property(str, notify=usageChanged)
    def usedText(self): return "¥13,605.24"
    @Property(str, notify=usageChanged)
    def todayText(self): return "今日已用 ¥267.86 · 608 次"
    @Property(str, notify=usageChanged)
    def todayAmountText(self): return "¥267.86"
    @Property(int, notify=usageChanged)
    def todayCount(self): return 608
    @Property(str, notify=usageChanged)
    def todayPromptTokensText(self): return "1.16B"
    @Property(str, notify=usageChanged)
    def todayCompletionTokensText(self): return "282K"
    @Property(str, notify=usageChanged)
    def todayTokensText(self): return "↑1.16B ↓282K"
    @Property(str, notify=usageChanged)
    def expiresText(self): return "永久有效"
    @Property(str, notify=statusChanged)
    def statusText(self): return "Codex 当前配置 · 每 60s 刷新 · 06:27:52"
    @Property("QVariantList", notify=logsChanged)
    def recentLogs(self):
        return [
            {"time": "09-12 06:25", "model": "gpt-5.6-sol",
             "tokens": "+54.8K / +309", "quotaText": "¥0.0634"},
            {"time": "09-12 06:25", "model": "gpt-5.6-sol",
             "tokens": "+59.3K / +112", "quotaText": "¥0.083"},
        ]
    @Property(str, notify=configSaved)
    def configPetImage(self): return ""
    @Property(int, notify=configSaved)
    def bubbleTimeoutSeconds(self): return 8
    @Property(int, notify=configSaved)
    def windowX(self): return -1
    @Property(int, notify=configSaved)
    def windowBottomY(self): return -1

    # ---- 账户钱包余额口径:令牌无限额度 → auto 应切到账户余额
    @Property(bool, notify=accountChanged)
    def accountReady(self): return True
    @Property(str, notify=accountChanged)
    def accountBalanceText(self): return "¥1.23K"
    @Property(str, notify=accountChanged)
    def accountUsedText(self): return "¥13,605.24"
    @Property(str, notify=accountChanged)
    def accountUpdatedText(self): return "07:12:34"
    @Property(str, notify=accountChanged)
    def accountErrorText(self): return ""
    @Property(str, notify=configSaved)
    def balanceSource(self): return "auto"
    @Property(str, notify=accountChanged)
    def activeBalanceSource(self): return "account"
    @Property(str, notify=usageChanged)
    def primaryBalanceText(self): return self.accountBalanceText
    @Property(str, notify=usageChanged)
    def primaryBalanceCaption(self): return "账户余额"
    @Property(bool, notify=usageChanged)
    def primaryBalanceNegative(self): return False

    @Slot()
    def refresh(self): pass
    @Slot(int, int)
    def savePosition(self, x, y): pass


class PetQmlLoadTests(unittest.TestCase):
    def _engine(self):
        engine = QQmlEngine()
        # 必须保留替身引用:被 Python 回收后 QML 侧会读到 null
        self._stub = StubPet()
        engine.rootContext().setContextProperty("PetStandalone", True)
        engine.rootContext().setContextProperty("NewApiPet", self._stub)
        return engine

    def setUp(self):
        # 保活 component / 窗口:QQmlComponent 被回收会连带销毁它创建的窗口
        self._components = []
        self._objects = []

    def _create(self, engine, name):
        component = QQmlComponent(engine)
        component.loadUrl(QUrl.fromLocalFile(str(PET_DIR / name)))
        self.assertFalse(
            component.isError(),
            f"{name} 加载失败: " + "; ".join(err.toString() for err in component.errors()),
        )
        self._components.append(component)
        obj = component.create()
        self.assertIsNotNone(
            obj, f"{name} 实例化失败: "
                 + "; ".join(err.toString() for err in component.errors()),
        )
        self._objects.append(obj)
        return obj

    def test_detail_card_shows_account_balance_and_secondary(self):
        """明细卡大数字走账户余额口径,同时把令牌额度摊开在旁边。"""
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("mode", "detail")
        window.setProperty("visible", True)
        APP.processEvents()

        self.assertEqual(window.property("primaryBalanceCaption"), "账户余额")
        self.assertEqual(window.property("primaryBalanceText"), "¥1.23K")
        # 令牌额度是 ∞,必须仍然能看到,不能被账户口径顶掉
        self.assertEqual(window.property("secondaryBalanceText"), "令牌额度 ∞")
        self.assertEqual(window.property("accountFreshText"), "账户余额更新于 07:12:34")

        panel = window.findChild(QQuickItem, "petPanel")
        self.assertIsNotNone(panel)
        texts = []
        _collect(panel, lambda i: i.metaObject().className().startswith("QQuickText"), texts)
        rendered = [str(item.property("text")) for item in texts]
        self.assertIn("账户余额", rendered)
        self.assertIn("¥1.23K", rendered)
        self.assertIn("令牌额度 ∞", rendered)

    def test_settings_dialog_content_fits_window(self):
        """设置窗口是固定高度,加字段必须同步改高度,否则按钮会被裁掉。"""
        engine = self._engine()
        dialog = self._create(engine, "PetSettingsDialog.qml")
        APP.processEvents()
        column = dialog.findChild(QQuickItem, "settingsFormColumn")
        self.assertIsNotNone(column, "设置表单 Column 没有 objectName,无法定位")
        used = float(column.property("implicitHeight"))
        available = float(dialog.property("height")) - 36  # anchors.margins: 18 * 2
        self.assertLessEqual(
            used, available,
            f"设置表单内容 {used}px 超出可用 {available}px,需要调大 dialog.height",
        )

    def test_settings_dialog_has_balance_source_chips(self):
        """设置窗口必须能切余额口径,并显示账户余额是否就绪。"""
        engine = self._engine()
        dialog = self._create(engine, "PetSettingsDialog.qml")
        dialog.setProperty("visible", True)
        APP.processEvents()

        root = dialog.findChild(QQuickItem, "settingsFormColumn")
        self.assertIsNotNone(root)
        texts = []
        _collect(root, lambda i: i.metaObject().className().startswith("QQuickText"), texts)
        rendered = [str(item.property("text")) for item in texts]
        for label in ("余额口径（大数字显示哪一套额度）", "自动", "令牌额度", "账户余额"):
            self.assertIn(label, rendered)
        # 替身的账户余额已就绪 → 提示行应显示"当前生效",而不是警告色文案
        hint = [text for text in rendered if text.startswith("当前生效")]
        self.assertEqual(len(hint), 1, f"没渲染出当前生效提示: {rendered}")
        self.assertIn("账户余额 ¥1.23K", hint[0])

        # 账户轮询间隔字段必须存在(值在 openForEdit 里从配置回填)
        field = dialog.findChild(QQuickItem, "accountIntervalField")
        self.assertIsNotNone(field, "缺少账户余额轮询间隔输入框")

    def test_pet_window_and_settings_dialog_instantiate(self):
        engine = self._engine()
        for name in ("PetWindow.qml", "PetSettingsDialog.qml"):
            with self.subTest(qml=name):
                self._create(engine, name)

    def test_pet_window_height_matches_panel_for_every_mode(self):
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        for mode, expected in EXPECTED_HEIGHTS.items():
            with self.subTest(mode=mode):
                window.setProperty("mode", mode)
                APP.processEvents()
                self.assertEqual(window.property("height"), expected)

    def test_pet_sprite_stays_inside_window_in_every_mode(self):
        """桌宠本体必须完整落在窗口内。

        曾经 pet 形态的桌宠 topMargin 用的是气泡模式的坐标,窗口又只有桌宠区那么高,
        结果桌宠被挤到窗口外:看不见、也点不到(鼠标事件全落到窗口外)。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()
        for mode in EXPECTED_HEIGHTS:
            with self.subTest(mode=mode):
                window.setProperty("mode", mode)
                APP.processEvents()
                panel = window.findChild(QQuickItem, "petPanel")
                sprite = panel.findChild(QQuickItem, "petSprite")
                self.assertIsNotNone(sprite, "桌宠没有 objectName")
                height = window.property("height")
                self.assertGreaterEqual(sprite.y(), 0, "桌宠顶边跑到窗口上方了")
                self.assertLessEqual(
                    sprite.y() + sprite.height(), height,
                    f"{mode} 形态下桌宠底边超出窗口({sprite.y() + sprite.height()} > {height})",
                )
                self.assertGreaterEqual(
                    height, PET_MODE_MIN_HEIGHT,
                    f"{mode} 形态窗口太矮,放不下桌宠",
                )

    # ---------------------------------------------------------------- 交互链路

    def _mouse_area_in(self, parent):
        hits = []
        _collect(parent, lambda i: i.metaObject().className().startswith("QQuickMouseArea"), hits)
        return hits

    def _click(self, window, item, button=Qt.LeftButton):
        QTest.mouseClick(window, button, Qt.NoModifier, self._center_of(window, item))
        APP.processEvents()

    @staticmethod
    def _center_of(window, item):
        """按当前布局重新取 item 中心对应的窗口坐标(形态切换后必须重取)。"""
        return item.mapToScene(
            QPoint(int(item.width() / 2), int(item.height() / 2))
        ).toPoint()

    def test_bubble_timer_pauses_on_hover_and_resumes_on_leave(self):
        """鼠标停进气泡时不能自动收起,离开后重新计时。

        这条路径历史上是 `petWindow.hideTimer.stop()` —— QML 取不到"根对象 id.子元素 id",
        于是每次进出气泡都抛 "Cannot call method 'stop' of undefined"。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        timer = window.findChild(QObject, "petHideTimer")
        self.assertIsNotNone(timer, "气泡计时器没有 objectName,无法定位")

        panel = window.findChild(QQuickItem, "petPanel")
        bubble_areas = self._mouse_area_in(panel.childItems()[1])
        self.assertTrue(bubble_areas, "气泡里没有 MouseArea")
        area = bubble_areas[0]
        inside = area.mapToScene(
            QPoint(int(area.width() / 2), int(area.height() / 2))
        ).toPoint()
        outside = QPoint(4, max(1, int(window.property("height")) - 6))

        captured = _capture_qml_warnings()
        try:
            self.assertTrue(timer.property("running"), "气泡出现后计时器应该是运行的")
            QTest.mouseMove(window, inside)
            APP.processEvents()
            self.assertFalse(timer.property("running"), "鼠标在气泡上时不应继续计时")

            QTest.mouseMove(window, outside)
            APP.processEvents()
            self.assertTrue(timer.property("running"), "鼠标离开气泡后应该重新计时")
            self.assertEqual(window.property("mode"), "bubble")
        finally:
            warnings = captured.stop()
        self.assertEqual(warnings, [], "气泡进出过程中出现 QML 运行期警告: " + " | ".join(warnings))

    def test_pet_interactions_switch_modes_without_qml_errors(self):
        """点击气泡 / 收起 / 右键菜单都要真的切形态,且不能有 QML 运行期报错。

        形态与气泡计时器属于 PetWindow,面板只是画面;历史上把窗口级函数
        误挂到面板上,结果是点击时才抛 "is not a function" 的 QML 警告。

        注意:桌宠自身有 onEntered → 弹气泡,off-screen 平台下 hover 状态不一定会
        因为窗口变矮而清掉,所以"收起之后到底停在 pet 还是 bubble"取决于鼠标位置;
        这里只断言"含有气泡的展示形态",不把 hover 的时序当成契约。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        captured = _capture_qml_warnings()
        try:
            panel = window.findChild(QQuickItem, "petPanel")
            self.assertIsNotNone(panel, "PetPanel 没有 objectName,无法定位")

            # 点击气泡 → 明细
            bubble_areas = self._mouse_area_in(panel.childItems()[1])
            self.assertTrue(bubble_areas, "气泡里没有 MouseArea")
            self._click(window, bubble_areas[0])
            self.assertEqual(window.property("mode"), "detail")

            # 收起 → 离开明细形态(桌宠 hover 会顺带把气泡弹出来)
            buttons = []
            _collect(panel, lambda i: i.metaObject().className().startswith("PetChipButton"), buttons)
            self.assertEqual(len(buttons), 2, "明细卡应该有刷新/收起两个按钮")
            self._click(window, buttons[1])
            self.assertNotEqual(window.property("mode"), "detail")
            self.assertIn(window.property("mode"), ("pet", "bubble"))

            # 悬停桌宠 → 弹气泡(桌宠在各形态都贴在窗口底部,所以一定点得到)
            pet_area = next(
                (item for item in panel.childItems()
                 if item.metaObject().className().startswith("QQuickMouseArea") and item.z() == 10),
                None,
            )
            self.assertIsNotNone(pet_area, "没找到桌宠交互层")
            self.assertGreaterEqual(
                window.property("height"), PET_MODE_MIN_HEIGHT,
                "pet 形态窗口太矮,桌宠会被裁到窗口外",
            )
            QTest.mouseMove(window, self._center_of(window, pet_area))
            APP.processEvents()
            self.assertEqual(window.property("mode"), "bubble")

            # 窗口变高后桌宠贴底,hit 区会跟着上移:重新取一次坐标再右键,
            # 否则右键落在旧坐标(窗口外)上会被直接丢掉。
            QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier,
                             self._center_of(window, pet_area))
            APP.processEvents()
            menu = panel.findChild(QQuickItem, "petContextMenu")
            self.assertIsNotNone(menu, "右键菜单没有 objectName")
            self.assertTrue(menu.isVisible(), "右键菜单没打开")
            column = menu.childItems()[0]
            self._click(window, column.childItems()[1])
            self.assertEqual(window.property("mode"), "detail")
        finally:
            warnings = captured.stop()
        self.assertEqual(warnings, [], "交互过程中出现 QML 运行期警告: " + " | ".join(warnings))


class PetDisplayCurrencyTests(unittest.TestCase):
    """currency=auto 必须跟随站点展示口径,而不是固定乘 7.3。"""

    def _controller(self, currency, site_display_type):
        from backend.newapi_pet import NewApiPet
        from backend.pet_config import PetConfig

        config = PetConfig(currency=currency, base_url="", api_key="")  # 无凭证 → 不发请求
        pet = NewApiPet("__no_such_config_path_for_test__.json", config)
        pet._site_display_type = site_display_type  # noqa: SLF001
        return pet

    def test_auto_follows_site_display_type(self):
        self.assertEqual(self._controller("auto", "USD")._display_params()[0],  # noqa: SLF001
                         "USD")
        self.assertEqual(self._controller("auto", "CNY")._display_params()[0],  # noqa: SLF001
                         "CNY")
        self.assertEqual(self._controller("auto", "TOKENS")._display_params()[0],  # noqa: SLF001
                         "TOKENS")
        self.assertEqual(self._controller("USD", "CNY")._display_params()[0],  # noqa: SLF001
                         "USD")
        self.assertEqual(self._controller("CNY", "USD")._display_params()[0],  # noqa: SLF001
                         "CNY")

    def test_auto_uses_site_conversion_parameters(self):
        # 跟随站点时用站点的 quota_per_unit / usd_exchange_rate,不用本地配置
        pet = self._controller("auto", "USD")
        pet._site_quota_per_unit = 500_000.0  # noqa: SLF001
        pet._site_usd_rate = 6.9  # noqa: SLF001
        currency, per_unit, rate = pet._display_params()  # noqa: SLF001
        self.assertEqual((currency, per_unit, rate), ("USD", 500_000.0, 6.9))
        # 站点余额 $914,320.57 在 auto 下应显示美元,而不是被乘成人民币
        quota = 914_320.57 * 500_000
        self.assertEqual(pet._fmt(quota), "$914,320.57")  # noqa: SLF001


class PetRequestHeadersTests(unittest.TestCase):
    """请求必须自带 User-Agent:Cloudflare 的 1010 规则会直接拒掉空 UA。"""

    def _pet(self):
        from backend.newapi_pet import NewApiPet
        from backend.pet_config import PetConfig

        return NewApiPet("__no_such_config_path_for_test__.json",
                         PetConfig(base_url="", api_key=""))

    def test_request_carries_user_agent_and_no_auth_when_public(self):
        from PySide6.QtNetwork import QNetworkRequest

        from backend.newapi_pet import USER_AGENT

        pet = self._pet()
        public = pet._build_request("https://example.com", "/api/status", "", False)  # noqa: SLF001
        self.assertEqual(str(public.header(QNetworkRequest.KnownHeaders.UserAgentHeader)),
                         USER_AGENT)
        # PySide6 的 hasRawHeader/rawHeader 收 str;rawHeader 返回 QByteArray,要 decode
        self.assertFalse(public.hasRawHeader("Authorization"))

        private = pet._build_request("https://example.com", "/api/usage/token/",  # noqa: SLF001
                                     "sk-test", True)
        self.assertEqual(bytes(private.rawHeader("Authorization")).decode(), "Bearer sk-test")

    def test_failure_messages_explain_common_statuses(self):
        from backend.newapi_pet import NewApiPet

        friendly = NewApiPet._friendly_failure
        self.assertIn("不是 new-api 站点", friendly(404, "HTTP 404"))
        self.assertIn("前置防护", friendly(403, "HTTP 403"))
        self.assertIn("未收到 HTTP 响应", friendly(None, "ConnectionRefused"))
        self.assertEqual(friendly(429, "HTTP 429"), "HTTP 429")


if __name__ == "__main__":
    unittest.main()
