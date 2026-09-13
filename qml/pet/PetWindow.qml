// ConfigPilot 余额桌宠:无边框置顶悬浮窗。
// 三类形态共用同一套栅格(卡片/气泡居中、桌宠固定在右下角,底边不动):
//   pet    只显示桌宠
//   bubble 桌宠 + 余额气泡(悬停/数据变化时自动出现)
//   detail 桌宠 + 明细面板(点击展开:额度、今日用量、Token、最近调用)
// 布局全部在 PetPanel 里,本文件只管窗口生命周期、位置、以及把数据喂给面板。
// 数据由 Python 端 NewApiPet 轮询 new-api 只读接口提供。
// 配色全部走 PrismQML 主题令牌(Fluent.Enums),面板/气泡/菜单/设置窗里的
// 结构件都换成 PrismQML 组件(清单见 PetPanel.qml 与 PetSettingsDialog.qml)。
//
// 窗口壳为什么仍是裸 Window:Fluent.WindowsCore 是"应用主窗壳"(标题栏、
// 导航栏、DWM 圆角阴影、四边缩放手柄、不透明 windowColor),套到桌宠身上会
// 直接毁掉"透明无边框置顶悬浮"这个形态本身;框架没有透明工具窗级别的壳,
// 所以这里保留裸 Window,只把配色与尺寸令牌化。
import QtQuick
import QtQuick.Window

import PrismQML as Fluent

Window {
    id: petWindow

    // ---------------------------------------------------------------- 基础窗口
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: Fluent.Enums.transparent
    width: 340
    // 窗口尺寸恒定,取所有形态里的最大高度:形态切换只改可见内容与窗口遮罩
    // (遮罩由 pet_bootstrap 在 Python 侧 setMask),窗口本身**永不 resize**。
    // 原因:透明无边框窗口 resize 时,系统要重建整块渲染表面,表现为整个悬浮窗
    // (含桌宠)闪 1~2 帧 —— 这正是"点一下闪一下"的来源。
    height: panel.maxPanelHeight
    // 底边固定在 bottomY。高度恒定后 y 也恒定,桌宠屏幕位置严格不动。
    y: bottomY >= 0 ? bottomY - height : 0
    title: "ConfigPilot 余额桌宠"
    visible: false

    readonly property bool standalone: typeof PetStandalone !== "undefined" ? PetStandalone : false
    readonly property bool managerReady: typeof PetManager !== "undefined" && PetManager !== null
    readonly property bool petReady: typeof NewApiPet !== "undefined" && NewApiPet !== null
    // 当前形态真正需要露出的高度:Python 侧据此设置窗口遮罩,其余部分对系统来说
    // 等于不存在(既不参与合成,也不接收鼠标)。
    readonly property int visibleContentHeight: panel.panelHeight

    // ---------------------------------------------------------------- 布局常量
    // 与 PetPanel 内部的固定行高一一对应,改动任一侧都要同步。
    // 明细卡片内容:32(头) + 1(分隔) + 52(额度卡) + 14(另一口径对照)
    //             + 34(Token 条) + 14(状态行) + 14(最近调用标题)
    //             + 90(三行日志) + 14(脚注)
    //             + 8*8(行间距) + 12*2(卡片内边距) ≈ 352
    //
    // 下面的尺寸是桌宠专属几何:Enums 里没有"悬浮窗宽度""桌宠图标边长"这类
    // 令牌,它们是本窗口的栅格定义,不是可复用的样式值,所以集中声明在此。
    readonly property int panelPadding: Fluent.Enums.spacing.m
    readonly property int panelWidth: 324
    readonly property int spriteSize: 120
    readonly property int spriteRightMargin: 14
    readonly property int detailContentHeight: 352
    // 气泡改成独立原生窗口(Fluent.TeachingTip)后不再占悬浮窗高度:
    // bubbleAreaHeight 归零、bubbleTop 归零,气泡形态与 pet 形态同高,
    // 气泡弹层自己的高度由 bubbleTipHeight 决定(尺寸是公开可配的)。
    readonly property int bubbleAreaHeight: 0
    readonly property int bubbleTipHeight: 84

    readonly property int cardTop: panelPadding
    // 桌宠区:必须放下 下边距 + 桌宠 + 与上方内容之间的空档
    readonly property int spriteBottomMargin: panelPadding
    readonly property int spriteGap: panelPadding * 2
    readonly property int petAreaHeight: spriteBottomMargin + spriteSize + spriteGap
    // 气泡锚点顶边(面板内部用它给弹层锚点定位)
    readonly property int bubbleTop: 0
    // 气泡形态的面板高度 = 气泡顶边 + 锚点(0) + 空档 + 桌宠 + 下边距
    readonly property int bubblePanelHeight: bubbleTop + bubbleAreaHeight + spriteGap
                                             + spriteSize + spriteBottomMargin

    property string mode: "bubble"
    // 面板是唯一布局来源:窗口高度跟随面板高度,底边保持不动。
    readonly property int panelHeight: panel.panelHeight

    property int bottomY: -1
    property string lastBalance: ""
    property string lastToday: ""
    // 真正关闭(进程退出)时才置位,避免退出流程被 onClosing 拦下。
    property bool forceClose: false

    // ---------------------------------------------------------------- 数据
    readonly property bool ready: petReady && NewApiPet.sourceReady
    readonly property bool failed: petReady && NewApiPet.hasError
    readonly property bool empty: petReady && NewApiPet.lowBalance
    readonly property bool alertState: failed || empty

    readonly property string tokenName: ready && NewApiPet.tokenName !== ""
                                         ? NewApiPet.tokenName : "NewAPI 令牌"
    // 余额:来源不可用或请求失败时退化为占位符,不展示过期数字
    readonly property string balanceText: !ready ? "—"
                                          : (failed ? "连接失败" : NewApiPet.balanceText)
    readonly property string todaySummary: ready ? NewApiPet.todayText : "—"
    readonly property string todayAmount: ready ? NewApiPet.todayAmountText : "—"
    readonly property string todayCountText: ready ? (NewApiPet.todayCount + " 次") : "—"
    readonly property string promptTokensText: ready ? NewApiPet.todayPromptTokensText : "—"
    readonly property string completionTokensText: ready ? NewApiPet.todayCompletionTokensText : "—"
    readonly property string grantedText: ready ? NewApiPet.grantedText : "—"
    readonly property string usedText: ready ? NewApiPet.usedText : "—"
    readonly property string expiresText: ready ? NewApiPet.expiresText : "—"
    readonly property string statusText: petReady ? NewApiPet.statusText : "桌宠未就绪"
    readonly property var logRows: ready ? NewApiPet.recentLogs : []
    readonly property string logFooterText: {
        var count = logRows.length
        if (count === 0) return "暂无调用记录"
        return "最近 " + count + " 条调用 · 数据来自 new-api 只读接口"
    }

    // ---- 余额口径:账户钱包余额 vs 令牌剩余额度(两个都摊开,不藏数字)
    readonly property string primaryBalanceText: petReady ? NewApiPet.primaryBalanceText : "—"
    readonly property string primaryBalanceCaption: petReady ? NewApiPet.primaryBalanceCaption : "剩余额度"
    readonly property bool primaryIsAccount: petReady && NewApiPet.activeBalanceSource === "account"
    readonly property bool primaryNegative: petReady && NewApiPet.primaryBalanceNegative
    readonly property bool accountReady: petReady && NewApiPet.accountReady
    readonly property string accountBalanceText: petReady ? NewApiPet.accountBalanceText : "—"
    readonly property string accountUsedText: petReady ? NewApiPet.accountUsedText : "—"
    // 左栏只显示"另一套口径"的数字;拿不到就留空,状态放右栏,不重复
    // 左栏只显示"另一套口径"的数字;拿不到就留空,状态放右栏,不重复
    readonly property string secondaryBalanceText: primaryIsAccount
                                                   ? ("令牌额度 " + balanceText)
                                                   : (accountReady ? ("账户余额 " + accountBalanceText)
                                                                   : "")
    // 右栏只显示账户余额的新鲜度或失败原因,与左栏不重复
    readonly property string accountFreshText: {
        if (!petReady) return ""
        if (accountReady) {
            var stamp = NewApiPet.accountUpdatedText
            return stamp === "" ? "" : "账户余额更新于 " + stamp
        }
        var brief = NewApiPet.accountErrorBrief
        return brief === "" ? "正在获取账户余额…" : ("账户余额获取失败：" + brief)
    }

    // ---------------------------------------------------------------- 生命周期
    onClosing: function (close) {
        // forceClose 由 quitApplication() / 独立模式置位:这次关闭是"进程要走了",
        // 绝不能顺手把 auto_show 开关关掉(否则退出程序=下次启动桌宠不出现)。
        if (forceClose || standalone) {
            forceClose = true
            return
        }
        // 集成模式:只隐藏窗口(实例保留,以便再次开启)并同步关掉开关。
        close.accepted = false
        hide()
        if (managerReady) PetManager.petWindowClosed()
    }

    // 右键菜单「退出程序」:退出整个应用(独立入口即桌宠进程本身)。
    // 走 Qt.quit() 而不是 close():关窗会把开关改掉,退出意图不该有副作用。
    function quitApplication() {
        forceClose = true
        Qt.quit()
    }

    function clampX(value) {
        var maxX = Screen.desktopAvailableWidth - width
        if (maxX < 0) return 0
        return Math.max(0, Math.min(value, maxX))
    }

    Component.onCompleted: {
        var startX = petReady ? NewApiPet.windowX : -1
        var startBottom = petReady ? NewApiPet.windowBottomY : -1
        if (startX === undefined || startX < 0) startX = Screen.desktopAvailableWidth - width - 16
        if (startBottom === undefined || startBottom < 0) startBottom = Screen.desktopAvailableHeight - 12
        x = clampX(startX)
        bottomY = startBottom
        showBubble()
    }

    // 形态与气泡计时器都属于窗口,面板只能通过下面这些函数/属性使用它们。
    // 注意:QML 里"根对象 id.子元素 id"取不到子元素(实测 typeof petWindow.hideTimer
    // 恒为 undefined),所以面板绝不能写 petWindow.hideTimer —— 只能走函数。
    function showBubble() {
        if (mode === "detail") return
        mode = "bubble"
        hideTimer.restart()
    }

    function hideBubble() {
        if (mode === "bubble") mode = "pet"
    }

    function toggleDetail() {
        if (mode === "detail") {
            mode = "pet"
        } else {
            mode = "detail"
            hideTimer.stop()
        }
    }

    // 给面板用的气泡计时器开关(面板读不到 hideTimer,只能调函数)
    function pauseBubbleTimer() {
        hideTimer.stop()
    }

    function resumeBubbleTimer() {
        if (mode === "bubble") hideTimer.restart()
    }

    // 气泡自动收起时长(由配置决定),面板用它做展示/调试
    readonly property int bubbleTimeoutMs: petReady ? NewApiPet.bubbleTimeoutSeconds * 1000 : 8000

    Timer {
        id: hideTimer
        objectName: "petHideTimer"
        interval: petWindow.bubbleTimeoutMs
        repeat: false
        onTriggered: petWindow.hideBubble()
    }

    Connections {
        target: petWindow.petReady ? NewApiPet : null
        function onUsageChanged() {
            // 只有余额/今日用量真正变化时才弹气泡,避免每个轮询周期打扰。
            var balance = NewApiPet.balanceText
            var today = NewApiPet.todayText
            var changed = balance !== petWindow.lastBalance || today !== petWindow.lastToday
            petWindow.lastBalance = balance
            petWindow.lastToday = today
            if (changed) petWindow.showBubble()
        }
        function onUsageBumped() { panel.bounce() }
        function onStatusChanged() {
            if (NewApiPet.hasError && petWindow.mode !== "detail") petWindow.showBubble()
        }
    }

    // ---------------------------------------------------------------- 面板
    PetPanel {
        id: panel
        // 锚定窗口底部:窗口高度是"最大形态"的常量,面板只占当前形态需要的高度,
        // 上方那块是透明区域,由窗口遮罩裁掉(不参与合成、不接收鼠标)。
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        height: panel.panelHeight
        mode: petWindow.mode
        panelPadding: petWindow.panelPadding
        panelWidth: petWindow.panelWidth
        petAreaHeight: petWindow.petAreaHeight
        detailContentHeight: petWindow.detailContentHeight
        bubbleAreaHeight: petWindow.bubbleAreaHeight
        bubbleTipHeight: petWindow.bubbleTipHeight
        bubbleTop: petWindow.bubbleTop
        cardTop: petWindow.cardTop
        spriteBottomMargin: petWindow.spriteBottomMargin
        spriteGap: petWindow.spriteGap
        spriteSize: petWindow.spriteSize
        spriteRightMargin: petWindow.spriteRightMargin
        ready: petWindow.ready
        failed: petWindow.failed
        empty: petWindow.empty
        alertState: petWindow.alertState
        petReady: petWindow.petReady
        managerReady: petWindow.managerReady
        tokenName: petWindow.tokenName
        balanceText: petWindow.balanceText
        todaySummary: petWindow.todaySummary
        todayAmount: petWindow.todayAmount
        todayCountText: petWindow.todayCountText
        promptTokensText: petWindow.promptTokensText
        completionTokensText: petWindow.completionTokensText
        grantedText: petWindow.grantedText
        usedText: petWindow.usedText
        expiresText: petWindow.expiresText
        statusText: petWindow.statusText
        logRows: petWindow.logRows
        logFooterText: petWindow.logFooterText
        primaryBalanceText: petWindow.primaryBalanceText
        primaryBalanceCaption: petWindow.primaryBalanceCaption
        primaryNegative: petWindow.primaryNegative
        secondaryBalanceText: petWindow.secondaryBalanceText
        accountFreshText: petWindow.accountFreshText
    }
}
