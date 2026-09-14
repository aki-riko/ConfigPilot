# coding: utf-8
"""桌宠 QML 的真实加载测试。

静态文本断言抓不到"QML 语法/结构被改坏"这类问题(桌宠面板是嵌套层数最深的
QML 之一,曾经因为少一个大括号导致卡片内容被裁掉)。这里用替身数据把
PetWindow / PetPanel 真正实例化一次,并核对三种形态的窗口高度。
"""

import os
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PET_DIR = ROOT / "qml" / "pet"

from PySide6.QtCore import Property, QObject, QMetaObject, QPoint, Qt, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


# 实例化 Window 需要 QGuiApplication(conftest.py 已保证平台与实例)
APP = QGuiApplication.instance()


def register_prismqml_on_engine(engine):
    """让桌宠 QML 能 `import PrismQML`:补模块路径并注册 ThemeManager。

    与 pet_main.py 的 register_types 对齐:桌宠 QML 的配色全部走
    Fluent.Enums 主题令牌,测试引擎必须能解析 PrismQML 模块。
    """
    import prismqml

    engine.addImportPath(os.path.dirname(prismqml.__file__))
    from prismqml import getThemeManager

    # 保活:QObject 被 Python 回收后 QML 单例会读到 null。
    register_prismqml_on_engine._keepalive = getThemeManager()
    engine.rootContext().setContextProperty(
        "ThemeManager", register_prismqml_on_engine._keepalive
    )
    return engine


def _collect(root, predicate, out):
    """递归收集 QQuickItem 子树中满足条件的节点。"""
    if predicate(root):
        out.append(root)
    for child in root.childItems():
        _collect(child, predicate, out)


def _collect_texts(root):
    """收集子树里所有可见文本(原生 Text 和 Fluent.Label 等复合文本都算)。"""
    items = []
    _collect(root, lambda i: i.metaObject().indexOfProperty("text") >= 0, items)
    return [str(item.property("text")) for item in items]


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


def _wait_for(predicate, timeout_ms=1200):
    """轮询等待异步完成的 QML 状态(框架弹层是开窗+动画的异步路径)。

    与 PrismQML tests/qml/test_menu_conventions.py 的同名助手同款。
    """
    from PySide6.QtCore import QCoreApplication, QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        if predicate():
            return True
        QCoreApplication.processEvents()
        QTest.qWait(30)
    return predicate()


# 与 PetWindow.qml / PetPanel.qml 里的布局常量保持一致
PANEL_PADDING = 8
SPRITE_SIZE = 120
SPRITE_BOTTOM_MARGIN = PANEL_PADDING
SPRITE_GAP = PANEL_PADDING * 2
CARD_TOP = PANEL_PADDING
DETAIL_CONTENT_HEIGHT = 352
# 气泡改成独立原生窗口(Fluent.TeachingTip)后不再占悬浮窗高度:
# 气泡形态与 pet 形态同高,弹层高度另由 PetWindow.bubbleTipHeight 决定。
BUBBLE_HEIGHT = 0
BUBBLE_TOP = 0
BUBBLE_TIP_HEIGHT = 84
EXPECTED_HEIGHTS = {
    "detail": CARD_TOP + DETAIL_CONTENT_HEIGHT + SPRITE_GAP + SPRITE_SIZE + SPRITE_BOTTOM_MARGIN,
    "bubble": BUBBLE_TOP + BUBBLE_HEIGHT + SPRITE_GAP + SPRITE_SIZE + SPRITE_BOTTOM_MARGIN,
    "pet": SPRITE_BOTTOM_MARGIN + SPRITE_SIZE + SPRITE_GAP,
}
# pet 形态的高度,需要能完整放下桌宠(否则桌宠会被裁到窗口外)
PET_MODE_MIN_HEIGHT = SPRITE_BOTTOM_MARGIN + SPRITE_SIZE


class StubPet(QObject):
    """桌宠控制器的替身:提供 QML 需要的全部只读属性。"""

    # 测试里可临时改成账户未就绪,验证界面不重复渲染"未就绪"
    account_ok = True
    account_error = ""

    usageChanged = Signal()
    logsChanged = Signal()
    statusChanged = Signal()
    configSaved = Signal()
    saveErrorChanged = Signal()
    usageBumped = Signal()
    sourcesChanged = Signal()
    accountChanged = Signal()

    def __init__(self, resources_dir: str = ""):
        super().__init__()
        self.refresh_calls = 0
        self.saved_positions = []
        # 形象解析用真实的 resources/pet,这样 QML 加载测试同时验证内置立绘接线。
        self._resources_dir = str(resources_dir or ROOT / "resources")

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
    @Property(bool, notify=usageChanged)
    def todayLowerBound(self): return False
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
    @Property(str, notify=configSaved)
    def petImageSource(self):
        from backend.pet_art import resolve_pet_image

        return resolve_pet_image(self.configPetImage, self._resources_dir)
    @Property("QVariantMap", notify=configSaved)
    def petImageFrames(self):
        from backend.pet_art import resolve_pet_frames

        return resolve_pet_frames(self.configPetImage, self._resources_dir)
    @Property("QVariantList", notify=configSaved)
    def petImagePresets(self):
        from backend.pet_art import list_pet_presets

        return [preset.to_map() for preset in list_pet_presets(self._resources_dir)]
    @Property(str, notify=configSaved)
    def defaultPetImageToken(self):
        from backend.pet_art import default_preset_token

        return default_preset_token(self._resources_dir)
    @Slot(str, result=str)
    def resolvePetImage(self, token):
        from backend.pet_art import resolve_pet_image

        return resolve_pet_image(token, self._resources_dir)
    @Property(int, notify=configSaved)
    def bubbleTimeoutSeconds(self): return 8
    @Property(int, notify=configSaved)
    def windowX(self): return -1
    @Property(int, notify=configSaved)
    def windowBottomY(self): return -1

    # ---- 账户钱包余额口径:令牌无限额度 → auto 应切到账户余额
    @Property(bool, notify=accountChanged)
    def accountReady(self): return self.account_ok
    @Property(str, notify=accountChanged)
    def accountBalanceText(self): return "¥1.23K" if self.account_ok else "—"
    @Property(str, notify=accountChanged)
    def accountUsedText(self): return "¥13,605.24"
    @Property(str, notify=accountChanged)
    def accountUpdatedText(self): return "07:12:34"
    @Property(str, notify=accountChanged)
    def accountErrorText(self): return "" if self.account_ok else self.account_error
    @Property(str, notify=accountChanged)
    def accountErrorBrief(self):
        if self.account_ok:
            return ""
        found = re.search(r"HTTP\s+(\d{3})", self.account_error)
        return f"HTTP {found.group(1)}" if found else self.account_error[:24]
    @Property(str, notify=configSaved)
    def balanceSource(self): return "auto"
    @Property(str, notify=accountChanged)
    def activeBalanceSource(self): return "account" if self.account_ok else "token"
    @Property(str, notify=usageChanged)
    def primaryBalanceText(self): return self.accountBalanceText if self.account_ok else "∞"
    @Property(str, notify=usageChanged)
    def primaryBalanceCaption(self): return "账户余额" if self.account_ok else "剩余额度"
    @Property(bool, notify=usageChanged)
    def primaryBalanceNegative(self): return False

    @Slot()
    def refresh(self):
        self.refresh_calls += 1

    @Slot(int, int)
    def savePosition(self, x, y):
        self.saved_positions.append((int(x), int(y)))


class StubManager(QObject):
    """PetManager 替身:记录「设置…」入口是否真的被调到。"""

    openSettingsRequested = Signal()

    def __init__(self):
        super().__init__()
        self.open_settings_calls = 0
        self.window_closed_calls = 0

    @Slot()
    def openSettings(self):
        self.open_settings_calls += 1

    @Slot()
    def petWindowClosed(self):
        self.window_closed_calls += 1


class PetQmlLoadTests(unittest.TestCase):
    def _engine(self, with_manager=False):
        engine = register_prismqml_on_engine(QQmlEngine())
        # 必须保留替身引用:被 Python 回收后 QML 侧会读到 null
        self._stub = StubPet()
        engine.rootContext().setContextProperty("PetStandalone", True)
        engine.rootContext().setContextProperty("NewApiPet", self._stub)
        if with_manager:
            self._manager = StubManager()
            engine.rootContext().setContextProperty("PetManager", self._manager)
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
        # Fluent.Label 是 QML 复合类型,元对象名是 Label_QMLTYPE_* 而不是裸 Text 的
        # QQuickText;这里按"有没有 text 属性"收集,与 _collect_texts 同一口径,
        # 否则换用框架 Label 之后断言会静默漏掉全部文本。
        rendered = _collect_texts(panel)
        self.assertIn("账户余额", rendered)
        self.assertIn("¥1.23K", rendered)
        self.assertIn("令牌额度 ∞", rendered)

    def test_built_in_pet_art_reaches_sprite_and_chips(self):
        """内置立绘经后端解析后真的落到 PetSprite.imagePath,设置窗芯片同步列出。

        这条串起"配置令牌 → backend.pet_art 解析 → QML 绑定"整条链:
        任何一环名字写错,桌宠就退回隐身/自绘形体,而界面看起来一切正常。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        sprite = window.findChild(QQuickItem, "petSprite")
        self.assertIsNotNone(sprite, "找不到桌宠本体节点")
        image_path = str(sprite.property("imagePath")).replace("\\", "/")
        self.assertTrue(image_path.lower().endswith("resources/pet/navigator/idle.png"),
                        f"桌宠没有用上默认内置立绘: {image_path!r}")
        self.assertTrue(Path(image_path).is_file(), f"立绘文件不存在: {image_path}")

        # 姿势帧要真的传到 PetSprite,否则动画状态机静默降级成单图(界面看不出问题)
        frames = sprite.property("frames")
        frames = frames.toVariant() if hasattr(frames, "toVariant") else frames
        self.assertEqual(sorted(frames), ["alert", "blink", "cheer", "idle", "sleepy", "wave"],
                         f"姿势帧没传到 PetSprite: {frames!r}")
        for role, path in frames.items():
            self.assertTrue(Path(path).is_file(), f"{role} 帧文件不存在: {path}")

        dialog = self._create(engine, "PetSettingsDialog.qml")
        # QML 的 var 数组读回来是 QJSValue,要先 toVariant() 才是 Python 列表
        choices = dialog.property("imageChoices")
        choices = choices.toVariant() if hasattr(choices, "toVariant") else choices
        tokens = [choice["token"] for choice in choices]
        self.assertEqual(tokens[0], "vector", "老的自绘形体必须仍然可选")
        self.assertIn("preset:navigator", tokens)
        self.assertEqual(dialog.property("activeImageToken"), "preset:navigator",
                         "配置留空时芯片应高亮清单里的默认立绘")
        self.assertTrue(Path(str(dialog.property("petImagePreviewPath"))).is_file())

    def test_pose_state_machine_priority_and_fallback(self):
        """姿势优先级 alert > 一次性姿势 > 基础姿势;缺帧/无帧要能降级而不是空白。"""
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()
        sprite = window.findChild(QQuickItem, "petSprite")
        self.assertIsNotNone(sprite)

        def shown():
            return str(sprite.property("shownPath")).replace("\\", "/").lower()

        self.assertTrue(shown().endswith("navigator/idle.png"), shown())

        sprite.setProperty("basePose", "sleepy")
        APP.processEvents()
        self.assertTrue(shown().endswith("navigator/sleepy.png"), shown())

        sprite.setProperty("activePose", "wave")
        APP.processEvents()
        self.assertTrue(shown().endswith("navigator/wave.png"), "一次性姿势应盖过基础姿势")

        sprite.setProperty("alert", True)
        APP.processEvents()
        self.assertTrue(shown().endswith("navigator/alert.png"), "告警优先级必须最高")

        # 收尾:告警解除 + 一次性姿势结束 → 回到基础姿势
        sprite.setProperty("alert", False)
        sprite.setProperty("activePose", "")
        APP.processEvents()
        self.assertTrue(shown().endswith("navigator/sleepy.png"), shown())

        # 未知角色帧 → 退回 idle,不能变成空白(空白会让桌宠"隐身")
        sprite.setProperty("activePose", "does_not_exist")
        APP.processEvents()
        self.assertTrue(shown().endswith("navigator/idle.png"), shown())

        # 无帧形象(用户自备图) → 退回主立绘路径,而不是留下空白
        sprite.setProperty("activePose", "")
        sprite.setProperty("frames", {})
        sprite.setProperty("imagePath", "D:/pics/custom_pet.png")
        APP.processEvents()
        self.assertTrue(shown().endswith("pics/custom_pet.png"), shown())

    def test_settings_form_scrolls_instead_of_overflowing(self):
        """设置表单由 Fluent.ScrollArea 承载:内容可以长过视口,但必须能滚动到。

        旧实现把"字段总高 <= 窗口高 - 边距"当人工约定,加一个字段就会被裁掉;
        现在正文在 ScrollArea 里,这条约定由框架接管,断言也随之迁移到滚动区。
        """
        engine = self._engine()
        dialog = self._create(engine, "PetSettingsDialog.qml")
        dialog.setProperty("visible", True)
        APP.processEvents()

        scroll = dialog.findChild(QQuickItem, "settingsScrollArea")
        self.assertIsNotNone(scroll, "设置窗口缺少 ScrollArea,长表单会被裁掉")
        column = dialog.findChild(QQuickItem, "settingsFormColumn")
        self.assertIsNotNone(column, "设置表单 Column 没有 objectName,无法定位")

        viewport = float(scroll.property("height"))
        self.assertGreater(viewport, 0, "滚动区没有高度")
        content_height = float(scroll.property("contentHeight"))
        self.assertGreater(content_height, 0, "ScrollArea 没有接管表单内容高度")

        # 表单比视口高时必须留下可滚动余量,否则底部按钮会被顶出可视区
        used = float(column.property("implicitHeight"))
        if used > viewport:
            self.assertGreater(
                content_height, viewport,
                f"表单 {used}px 高于视口 {viewport}px,但滚动区没有产生滚动余量",
            )

    def test_settings_dialog_has_balance_source_chips(self):
        """设置窗口必须能切余额口径,并显示账户余额是否就绪。"""
        engine = self._engine()
        dialog = self._create(engine, "PetSettingsDialog.qml")
        dialog.setProperty("visible", True)
        APP.processEvents()

        root = dialog.findChild(QQuickItem, "settingsFormColumn")
        self.assertIsNotNone(root)
        rendered = _collect_texts(root)
        for label in ("余额口径", "大数字显示哪一套额度", "自动", "令牌额度", "账户余额"):
            self.assertIn(label, rendered)
        # 替身的账户余额已就绪 → 提示行应显示"当前生效",而不是警告色文案
        hint = [text for text in rendered if text.startswith("当前生效")]
        self.assertEqual(len(hint), 1, f"没渲染出当前生效提示: {rendered}")
        self.assertIn("账户余额 ¥1.23K", hint[0])

        # 账户轮询间隔字段必须存在(值在 openForEdit 里从配置回填)
        field = dialog.findChild(QQuickItem, "accountIntervalField")
        self.assertIsNotNone(field, "缺少账户余额轮询间隔输入框")

    def test_account_not_ready_row_does_not_duplicate_message(self):
        """账户余额未就绪时,左右两栏不能各写一遍同样的话。"""

        class NotReadyStub(StubPet):
            account_ok = False
            account_error = "HTTP 404（站点未提供 new-api 查询接口，可能不是 new-api 站点）"

        engine = register_prismqml_on_engine(QQmlEngine())
        stub = NotReadyStub()
        engine.rootContext().setContextProperty("PetStandalone", True)
        engine.rootContext().setContextProperty("NewApiPet", stub)
        component = QQmlComponent(engine)
        component.loadUrl(QUrl.fromLocalFile(str(PET_DIR / "PetWindow.qml")))
        self.assertFalse(component.isError())
        window = component.create()
        APP.processEvents()

        self.assertEqual(str(window.property("secondaryBalanceText")), "",
                         "左栏在未就绪时不该重复写状态")
        fresh = str(window.property("accountFreshText"))
        self.assertIn("HTTP 404", fresh, f"右栏应给出简短失败原因: {fresh}")
        self.assertEqual(fresh.count("未就绪"), 0)
        # 未就绪 → 大数字退回令牌口径,不能显示空值
        self.assertEqual(window.property("primaryBalanceCaption"), "剩余额度")
        self.assertEqual(window.property("primaryBalanceText"), "∞")

    def test_panel_receives_readiness_flags(self):
        """面板必须拿到 petReady/managerReady。

        这两个标志漏注入时是 undefined(假),会让「刷新」「设置…」「立即刷新」
        和拖动后的存位置四处入口静默失效,而且不报任何 QML 错误 —— 曾经因此
        表现为「设置窗口弹不出来」。
        """
        engine = self._engine(with_manager=True)
        window = self._create(engine, "PetWindow.qml")
        APP.processEvents()
        panel = window.findChild(QQuickItem, "petPanel")
        self.assertTrue(bool(panel.property("petReady")), "petReady 没注入面板")
        self.assertTrue(bool(panel.property("managerReady")), "managerReady 没注入面板")

    def test_refresh_button_and_settings_menu_reach_backend(self):
        """明细卡「刷新」和右键菜单「设置…」必须真的打到后端。"""
        engine = self._engine(with_manager=True)
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("mode", "detail")
        window.setProperty("visible", True)
        # 过渡动画要跑完再点:期间按钮还在淡入上浮,点击会落空
        self.assertTrue(self._settle(window, "detail"), "明细卡过渡没有收敛,无法稳定点击")
        panel = window.findChild(QQuickItem, "petPanel")

        refresh_btn = window.findChild(QQuickItem, "petRefreshButton")
        self.assertIsNotNone(refresh_btn, "刷新按钮没有 objectName")
        self._click(window, refresh_btn)
        self.assertEqual(self._stub.refresh_calls, 1, "刷新按钮没打到 NewApiPet.refresh()")

        # 右键 → 框架 ContextMenu 弹出 → 触发「设置…」动作
        pet_area = next(i for i in panel.childItems()
                        if i.metaObject().className().startswith("QQuickMouseArea") and i.z() == 10)
        point = self._center_of(window, pet_area)
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, point)
        APP.processEvents()
        menu = panel.findChild(QObject, "petContextMenu")
        self.assertIsNotNone(menu, "右键菜单没有 objectName")
        self.assertTrue(_wait_for(lambda: menu.property("isOpen")), "右键菜单没打开")
        settings_action = menu.getAction("settings")
        self.assertIsNotNone(settings_action, "菜单缺少「设置…」动作")
        # QML 声明的信号在 Python 侧要用 invokeMethod 触发
        QMetaObject.invokeMethod(settings_action, "triggered")
        self.assertTrue(
            _wait_for(lambda: not menu.property("isOpen")
                      and not menu.property("isClosing")),
            "触发动作后菜单应自动关闭")
        self.assertEqual(self._manager.open_settings_calls, 1,
                         "「设置…」没打到 PetManager.openSettings()")

    def test_dragging_pet_saves_position(self):
        """拖动桌宠后要落盘位置,否则下次启动/收起展开会跳回原位。"""
        engine = self._engine(with_manager=True)
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()
        panel = window.findChild(QQuickItem, "petPanel")
        pet_area = next(i for i in panel.childItems()
                        if i.metaObject().className().startswith("QQuickMouseArea") and i.z() == 10)
        start = self._center_of(window, pet_area)
        QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
        APP.processEvents()
        QTest.mouseMove(window, QPoint(start.x() - 24, start.y() - 14))
        APP.processEvents()
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier,
                           QPoint(start.x() - 24, start.y() - 14))
        APP.processEvents()
        self.assertEqual(len(self._stub.saved_positions), 1,
                         "拖动后没有调用 savePosition")

    def test_pet_window_and_settings_dialog_instantiate(self):
        engine = self._engine()
        for name in ("PetWindow.qml", "PetSettingsDialog.qml"):
            with self.subTest(qml=name):
                self._create(engine, name)

    def test_pet_window_height_matches_panel_for_every_mode(self):
        """窗口高度最终等于各形态的面板高度。

        高度本身不做逐帧动画(逐帧 resize 会拖死主线程),但**收缩**要等内容
        淡出跑完才收,所以这里断言的是最终收敛值。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        sizes = set()
        for mode, expected in EXPECTED_HEIGHTS.items():
            with self.subTest(mode=mode):
                window.setProperty("mode", mode)
                self.assertTrue(
                    _wait_for(lambda: window.property("visibleContentHeight") == expected),
                    f"{mode} 形态的可见高度没有收敛到 {expected} "
                    f"(当前 {window.property('visibleContentHeight')})",
                )
                sizes.add((window.property("width"), window.property("height")))

        # 窗口本身尺寸必须恒定:透明无边框窗口 resize 会让系统重建渲染表面,
        # 表现为整个悬浮窗(含桌宠)闪 1~2 帧 —— 这就是"点一下闪一下"的来源。
        self.assertEqual(len(sizes), 1, f"形态切换改了窗口尺寸: {sizes}")
        width, height = sizes.pop()
        self.assertEqual(width, 484)
        self.assertEqual(height, max(EXPECTED_HEIGHTS.values()),
                         "窗口高度应恒定为最大形态高度")

    def test_attach_pet_window_mask_smoke(self):
        """像素遮罩装配冒烟:计时器挂上、离屏窗口不抛异常、保底矩形先铺。"""
        from backend.pet_bootstrap import _attach_pet_window_mask

        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        _attach_pet_window_mask(window)
        APP.processEvents()
        self.assertTrue(hasattr(window, "_pet_mask_debounce"))
        self.assertTrue(hasattr(window, "_pet_mask_followup"))
        self.assertTrue(hasattr(window, "_pet_mask_sprite"),
                        "姿势钩子必须挂到 petSprite,否则换姿势遮罩会失配")
        self.assertFalse(window.mask().isEmpty(),
                         "装配后必须先铺保底矩形,桌宠不能点不到")

    def test_shrink_waits_for_fade_out(self):
        """收缩时可见区必须等明细卡淡出结束再收。

        防回流门禁 —— 明细卡比气泡高,可见区若立刻缩矮,正在淡出的卡片会被
        下沿一路裁掉,看起来像"卡片被抽走"。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("mode", "detail")
        APP.processEvents()
        self.assertEqual(
            window.property("visibleContentHeight"), EXPECTED_HEIGHTS["detail"])

        window.setProperty("mode", "bubble")
        APP.processEvents()
        self.assertEqual(
            window.property("visibleContentHeight"), EXPECTED_HEIGHTS["detail"],
            "可见区在明细卡淡出前就缩了,卡片会被下沿裁掉",
        )
        self.assertTrue(
            _wait_for(lambda: window.property("visibleContentHeight")
                      == EXPECTED_HEIGHTS["bubble"]),
            "可见区最终没有收缩到气泡形态",
        )

    def test_mode_switch_animates_content_instead_of_jumping(self):
        """形态切换必须有内容过渡:新内容淡入上浮、旧内容淡出下沉,不能瞬变。

        防回流门禁 —— 旧做法是 visible 直接切 mode,内容"啪"地出现/消失(0 过渡)。
        这里用轮询采样中间态,而不是断言某一帧的具体数值:动画推进速度随平台
        (offscreen / 真实窗口)不同,只有"确实出现过中间态"才是稳定合同。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        window.setProperty("mode", "bubble")
        APP.processEvents()

        panel = window.findChild(QQuickItem, "petPanel")
        self.assertIsNotNone(panel)
        detail = panel.childItems()[0]
        bubble = panel.childItems()[1]

        window.setProperty("mode", "detail")
        detail_mid = bubble_mid = shift_mid = False
        for _ in range(30):
            # 必须用 QTest.qWait 而不是裸 processEvents:后者在 offscreen 平台
            # 不会驱动 QML 动画,采样到的永远是两端状态。
            QTest.qWait(20)
            if 0.01 < float(detail.property("opacity")) < 0.99:
                detail_mid = True
            if 0.01 < float(bubble.property("opacity")) < 0.99:
                bubble_mid = True
            if float(detail.property("shiftY")) > 0.01:
                shift_mid = True
            if detail_mid and bubble_mid and shift_mid:
                break

        self.assertTrue(detail_mid, "明细卡没有淡入中间态,过渡是瞬变")
        self.assertTrue(bubble_mid, "气泡没有淡出中间态,过渡是瞬变")
        self.assertTrue(shift_mid, "明细卡没有上浮位移,过渡只有透明度没有动作")

        self.assertTrue(
            _wait_for(lambda: float(detail.property("opacity")) >= 0.999),
            "明细卡淡入没有收敛",
        )
        self.assertTrue(
            _wait_for(lambda: float(detail.property("shiftY")) <= 0.01),
            "明细卡位移没有收敛",
        )
        self.assertTrue(
            _wait_for(lambda: int(bubble.property("visible")) == 0),
            "淡出结束后气泡应真正隐藏(否则它会继续吃鼠标事件)",
        )

    def test_pet_sprite_stays_inside_window_in_every_mode(self):
        """桌宠本体必须完整落在窗口内。

        曾经 pet 形态的桌宠 topMargin 用的是气泡模式的坐标,窗口又只有桌宠区那么高,
        结果桌宠被挤到窗口外:看不见、也点不到(鼠标事件全落到窗口外)。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()
        for mode, visible in EXPECTED_HEIGHTS.items():
            with self.subTest(mode=mode):
                window.setProperty("mode", mode)
                # 可见区带过渡(收缩要等淡出),不先收敛的话 sprite.y 还在动
                _wait_for(lambda: window.property("visibleContentHeight") == visible)
                panel = window.findChild(QQuickItem, "petPanel")
                sprite = panel.findChild(QQuickItem, "petSprite")
                self.assertIsNotNone(sprite, "桌宠没有 objectName")
                # 面板锚定窗口底部,面板高度就是可见区高度
                self.assertEqual(
                    panel.property("height"), visible,
                    f"{mode} 形态下可见区高度与面板高度不一致",
                )
                self.assertGreaterEqual(sprite.y(), 0, "桌宠顶边跑到可见区上方了")
                self.assertLessEqual(
                    sprite.y() + sprite.height(), visible,
                    f"{mode} 形态下桌宠底边超出可见区"
                    f"({sprite.y() + sprite.height()} > {visible})",
                )
                self.assertGreaterEqual(
                    visible, PET_MODE_MIN_HEIGHT,
                    f"{mode} 形态可见区太矮,放不下桌宠",
                )

    # ---------------------------------------------------------------- 交互链路

    def _mouse_area_in(self, parent):
        hits = []
        _collect(parent, lambda i: i.metaObject().className().startswith("QQuickMouseArea"), hits)
        return hits

    def _settle(self, window, mode):
        """等形态过渡动画收敛。

        切换后 200ms 内新内容还在淡入 + 上浮,控件中心坐标一直在变,这时点击
        会落空;所以凡是要点明细卡里按钮的用例,都必须先等它停稳。
        """
        panel = window.findChild(QQuickItem, "petPanel")
        item = panel.childItems()[0 if mode == "detail" else 1]
        return _wait_for(
            lambda: float(item.property("opacity")) >= 0.999
                    and float(item.property("shiftY")) <= 0.01,
            timeout_ms=1500,
        )

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

        气泡改成独立原生窗口(Fluent.TeachingTip)后,交互层在弹层窗口里,
        所以要驱动的是那个弹层窗口,而不是悬浮窗。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        timer = window.findChild(QObject, "petHideTimer")
        self.assertIsNotNone(timer, "气泡计时器没有 objectName,无法定位")

        panel = window.findChild(QQuickItem, "petPanel")
        tip = panel.findChild(QObject, "petBubbleTip")
        self.assertIsNotNone(tip, "气泡锚点里没有 TeachingTip")
        self.assertTrue(_wait_for(lambda: tip.property("_popupWindow") is not None),
                        "窗口首帧上屏后气泡弹层应出现")
        popup = tip.property("_popupWindow")

        bubble_areas = self._mouse_area_in(popup.contentItem())
        self.assertTrue(bubble_areas, "气泡弹层里没有 MouseArea")
        area = bubble_areas[0]
        inside = QPoint(int(area.width() / 2), int(area.height() / 2))
        outside = QPoint(-8, -8)

        captured = _capture_qml_warnings()
        try:
            self.assertTrue(timer.property("running"), "气泡出现后计时器应该是运行的")
            QTest.mouseMove(popup, inside)
            APP.processEvents()
            self.assertFalse(timer.property("running"), "鼠标在气泡上时不应继续计时")

            QTest.mouseMove(popup, outside)
            APP.processEvents()
            self.assertTrue(timer.property("running"), "鼠标离开气泡后应该重新计时")
        finally:
            warnings = captured.stop()
        self.assertEqual(warnings, [], "气泡进出过程中出现 QML 运行期警告: " + " | ".join(warnings))

    def test_bubble_waits_for_first_frame_before_show(self):
        """首次启动错位回归:窗口首帧上屏前气泡绝不能弹。

        悬浮窗的原生位置在 map 时才生效且不产生 xChanged/yChanged,弹层若在
        首帧前 show() 会按 (0,0) 定格在屏幕左上角、永不纠正(用户截图实锤)。
        """
        engine = self._engine()
        window = self._create(engine, "PetWindow.qml")
        APP.processEvents()
        panel = window.findChild(QQuickItem, "petPanel")
        tip = panel.findChild(QObject, "petBubbleTip")
        self.assertIsNotNone(tip, "气泡锚点里没有 TeachingTip")
        self.assertIsNone(tip.property("_popupWindow"),
                          "窗口还没上屏就弹气泡,会按未映射的窗口位置定格左上角")
        window.setProperty("visible", True)
        self.assertTrue(_wait_for(lambda: tip.property("_popupWindow") is not None),
                        "首帧上屏后气泡应自动弹出")

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

            # 点击气泡 → 明细。气泡现在是独立原生窗口,交互层在弹层里。
            tip = panel.findChild(QObject, "petBubbleTip")
            self.assertIsNotNone(tip, "气泡锚点里没有 TeachingTip")
            self.assertTrue(_wait_for(lambda: tip.property("_popupWindow") is not None),
                            "窗口首帧上屏后气泡弹层应出现")
            popup = tip.property("_popupWindow")
            bubble_areas = self._mouse_area_in(popup.contentItem())
            self.assertTrue(bubble_areas, "气泡弹层里没有 MouseArea")
            QTest.mouseClick(popup, Qt.LeftButton, Qt.NoModifier,
                             self._center_of(popup, bubble_areas[0]))
            APP.processEvents()
            self.assertEqual(window.property("mode"), "detail")
            # 过渡跑完再点收起,否则按钮还在淡入上浮,点击会落空
            self.assertTrue(self._settle(window, "detail"), "明细卡过渡没有收敛,无法稳定点击")

            # 收起 → 离开明细形态(桌宠 hover 会顺带把气泡弹出来)
            collapse_btn = window.findChild(QQuickItem, "petCollapseButton")
            self.assertIsNotNone(collapse_btn, "明细卡应该有「收起」按钮")
            self._click(window, collapse_btn)
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
            menu = panel.findChild(QObject, "petContextMenu")
            self.assertIsNotNone(menu, "右键菜单没有 objectName")
            self.assertTrue(_wait_for(lambda: menu.property("isOpen")), "右键菜单没打开")
            detail_action = menu.getAction("detail")
            self.assertIsNotNone(detail_action, "菜单缺少「明细面板」动作")
            QMetaObject.invokeMethod(detail_action, "triggered")
            self.assertTrue(
                _wait_for(lambda: not menu.property("isOpen")
                          and not menu.property("isClosing")),
                "触发动作后菜单应自动关闭")
            self.assertEqual(window.property("mode"), "detail")
        finally:
            warnings = captured.stop()
        self.assertEqual(warnings, [], "交互过程中出现 QML 运行期警告: " + " | ".join(warnings))


    def test_context_menu_quit_action_exits_program(self):
        """右键菜单里只剩「退出程序」:退出整个应用，不该顺手把桌宠开关关掉。"""
        engine = self._engine(with_manager=True)
        window = self._create(engine, "PetWindow.qml")
        window.setProperty("visible", True)
        APP.processEvents()

        panel = window.findChild(QQuickItem, "petPanel")
        menu = panel.findChild(QObject, "petContextMenu")
        self.assertIsNotNone(menu, "右键菜单没有 objectName")

        quit_action = menu.getAction("quitApp")
        self.assertIsNotNone(quit_action, "菜单缺少「退出程序」动作")
        self.assertEqual(str(quit_action.property("text")), "退出程序")
        self.assertIsNone(menu.getAction("quit"), "旧的「退出桌宠」动作还留着")
        self.assertNotIn("退出桌宠", _collect_texts(panel))

        QMetaObject.invokeMethod(quit_action, "triggered")
        APP.processEvents()

        # forceClose 置位后，退出流程里补发的关闭不会再走 petWindowClosed()
        self.assertTrue(bool(window.property("forceClose")),
                        "退出程序必须置位 forceClose")
        self.assertEqual(self._manager.window_closed_calls, 0,
                         "退出程序不该把 auto_show 开关改掉")
        self.assertTrue(bool(window.property("visible")),
                        "退出动作不该自己把桌宠窗口关掉")


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


    def test_account_error_brief_keeps_only_status_code(self):
        from backend.newapi_pet import NewApiPet
        from backend.pet_config import PetConfig

        pet = NewApiPet("__no_such_config_path_for_test__.json",
                        PetConfig(base_url="", api_key=""))
        cases = {
            "HTTP 404（站点未提供 new-api 查询接口，可能不是 new-api 站点）": "HTTP 404",
            "请求失败：HTTP 403：invalid access token": "HTTP 403",
            "ConnectionRefused: 连接被拒绝": "ConnectionRefused",
            "": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                pet._account_error = raw  # noqa: SLF001
                self.assertEqual(pet.accountErrorBrief, expected)


class PetTodayLogStoreTests(unittest.TestCase):
    """控制器接线:接口窗口按 request_id 并入本地缓存,「今日已用」覆盖全天;
    离线缺口加"≥"下限;落盘后重启不清零。"""

    def setUp(self):
        from datetime import datetime
        now = datetime.now()
        if now.hour == 0 and now.minute < 40:
            self.skipTest("临近本地零点,窗口时间戳会跨天,跳过以免假失败")

    def _pet(self, log_store_path=""):
        from backend.newapi_pet import NewApiPet
        from backend.pet_config import PetConfig

        config = PetConfig(currency="USD", base_url="", api_key="")
        return NewApiPet("__no_such_config_path_for_test__.json", config,
                         log_store_path=log_store_path)

    @staticmethod
    def _rows(start, count, step=1):
        import time as _t
        now_ts = int(_t.time())
        return [
            {
                "id": i % 1000 + 1,  # 相对序号:真实站点每次请求重排,不可作键
                "request_id": f"req-{i}",
                "created_at": now_ts - i * step,
                "type": 2,
                "quota": 100 + i,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "model_name": "gpt-test",
            }
            for i in range(start, start + count)
        ]

    def _poll(self, pet, rows):
        pet._pending = {"logs": True}  # noqa: SLF001
        pet._staged = {}  # noqa: SLF001
        pet._handle_logs({"success": True, "data": rows})  # noqa: SLF001
        APP.processEvents()

    @staticmethod
    def _wait_saved(pet):
        """等后台落盘线程把这一轮写完,避免临时目录清理竞态。"""
        for _ in range(100):
            APP.processEvents()
            if not pet._log_store_saving and not pet._log_store.dirty:  # noqa: SLF001
                return
            QTest.qWait(20)

    def test_accumulates_beyond_1000_window_with_lower_bound(self):
        pet = self._pet()
        self._poll(pet, self._rows(0, 1000))          # 启动即满窗 → 更早的今天没拿到
        self.assertEqual(pet.todayCount, 1000)
        self.assertTrue(pet.todayLowerBound)
        self._poll(pet, self._rows(200, 1000))        # 窗口滑掉前 200 条,本地仍保留
        self.assertEqual(pet.todayCount, 1200)
        self.assertIn("≥", pet.todayText)
        self.assertTrue(pet.todayAmountText.startswith("≥"))

    def test_continuous_polling_stays_exact(self):
        pet = self._pet()
        self._poll(pet, self._rows(0, 500))           # 窗口不满 → 覆盖到零点,数字可信
        self.assertFalse(pet.todayLowerBound)
        self._poll(pet, self._rows(100, 1000))        # 满窗但与本地重叠 → 仍完整
        self.assertEqual(pet.todayCount, 1100)
        self.assertFalse(pet.todayLowerBound)

    def test_logs_failure_keeps_accumulated_store(self):
        pet = self._pet()
        self._poll(pet, self._rows(0, 10))
        before = pet.todayCount
        pet._pending = {"logs": True}  # noqa: SLF001
        pet._handle_logs({"success": False, "message": "boom"})  # noqa: SLF001
        APP.processEvents()
        self.assertEqual(pet.todayCount, before)

    def test_restart_restores_from_disk(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "pet_logs.json")
            pet1 = self._pet(path)
            self._poll(pet1, self._rows(0, 10))
            self._wait_saved(pet1)
            self.assertTrue(Path(path).is_file(), "日志缓存必须已落盘")

            pet2 = self._pet(path)                    # 模拟重启
            self._poll(pet2, self._rows(5, 10))       # 重叠 req-5..9,新增 req-10..14
            self.assertEqual(pet2.todayCount, 15)
            self.assertFalse(pet2.todayLowerBound)
            self._wait_saved(pet2)                    # 等写完再退出,避免清理竞态


class PetMaskRegionBuilderTests(unittest.TestCase):
    """_build_mask_region 纯函数:alpha≥16 的游程进区域、DPR 映射正确、胀边盖住动画位移。

    margin=0 用来单验"扫描 + DPR 映射"这层语义;胀边是另一层,单独测。
    """

    @staticmethod
    def _image(width, height, rects, alpha=255):
        from PySide6.QtGui import QColor, QImage, QPainter

        img = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(img)
        color = QColor(255, 0, 0, alpha)
        for x, y, w, h in rects:
            painter.fillRect(x, y, w, h, color)
        painter.end()
        return img

    def _build(self, img, dpr=1.0, margin=0):
        from backend.pet_bootstrap import _build_mask_region

        return _build_mask_region(bytes(img.constBits()), img.bytesPerLine(),
                                  img.width(), img.height(), dpr, margin)

    def test_only_opaque_runs_are_kept(self):
        region = self._build(self._image(40, 20, [(5, 3, 10, 7), (25, 12, 5, 5)]))
        self.assertTrue(region.contains(QPoint(10, 6)))
        self.assertTrue(region.contains(QPoint(27, 14)))
        self.assertFalse(region.contains(QPoint(20, 6)))    # 两块之间的横向空白
        self.assertFalse(region.contains(QPoint(10, 15)))   # 纵向空白
        self.assertFalse(region.contains(QPoint(1, 1)))     # 全透明角落

    def test_low_alpha_noise_excluded(self):
        region = self._build(self._image(30, 10, [(5, 2, 10, 6)], alpha=8))
        self.assertTrue(region.isEmpty(), "alpha 8 < 阈值 16,不该进遮罩")

    def test_high_dpi_maps_to_logical_coords(self):
        # dpr=2:设备图 80×40,设备矩形 (20,10,20,10) → 逻辑 (10,5,10,5)
        region = self._build(self._image(80, 40, [(20, 10, 20, 10)]), dpr=2.0)
        self.assertTrue(region.contains(QPoint(12, 7)))
        self.assertTrue(region.contains(QPoint(19, 9)))
        self.assertFalse(region.contains(QPoint(8, 3)))
        self.assertFalse(region.contains(QPoint(21, 11)))

    def test_transparent_image_gives_empty_region(self):
        self.assertTrue(self._build(self._image(20, 20, [])).isEmpty())

    def test_margin_widens_region_but_noise_still_excluded(self):
        # 胀边:横向/纵向各向外 4 逻辑像素;alpha 太低的噪声块胀完也不该出现
        img = self._image(60, 40, [(20, 15, 8, 6)])
        tight = self._build(img, margin=0)
        wide = self._build(img, margin=4)
        self.assertFalse(tight.contains(QPoint(17, 15)))
        self.assertTrue(wide.contains(QPoint(16, 11)), "胀边后应覆盖到左上 4 像素")
        self.assertTrue(wide.contains(QPoint(31, 24)))
        self.assertFalse(wide.contains(QPoint(10, 10)), "离剪影 10 像素以上不该被胀进来")
        self.assertTrue(self._build(self._image(60, 40, [(20, 15, 8, 6)], alpha=8),
                                    margin=6).isEmpty())

    def test_default_margin_covers_sway_displacement(self):
        """默认胀边必须盖住"遮罩定格在摆动一端"的最坏位移(头顶 ≈ 8.2 逻辑像素)。"""
        from backend.pet_bootstrap import _MASK_MARGIN_LOGICAL

        self.assertGreaterEqual(_MASK_MARGIN_LOGICAL, 9)

    def test_production_default_margin_applied(self):
        img = self._image(60, 40, [(20, 15, 8, 6)])
        from backend.pet_bootstrap import _MASK_MARGIN_LOGICAL, _build_mask_region

        default = _build_mask_region(bytes(img.constBits()), img.bytesPerLine(),
                                     img.width(), img.height(), 1.0)
        self.assertTrue(default.contains(QPoint(20 - _MASK_MARGIN_LOGICAL + 1, 15)))
        self.assertTrue(default.contains(QPoint(28 + _MASK_MARGIN_LOGICAL - 1, 21)))


if __name__ == "__main__":
    unittest.main()
