// ConfigPilot 主窗口
import QtQuick

import PrismQML as Fluent
import "dialogs"

QtObject {
    id: root

    readonly property int windowWidth: 980
    readonly property int windowHeight: 640
    readonly property string windowTitle: "ConfigPilot"

    function iconPath(name) {
        return (typeof FluentIconsDir !== "undefined" ? FluentIconsDir : "") + name + ".svg"
    }

    function resourceIconPath(name) {
        return Qt.resolvedUrl("../resources/" + name + ".svg")
    }

    property var navItems: [
        { "text": "Codex", "icon": resourceIconPath("chatgpt") },
        { "text": "Claude", "icon": resourceIconPath("claude") }
    ]

    property var bottomNavItems: [
        { "text": "设置", "icon": iconPath("Settings"), "key": "AboutView" }
    ]

    property var pagePaths: [
        Qt.resolvedUrl("views/CodexView.qml"),
        Qt.resolvedUrl("views/ClaudeDesktopView.qml"),
        Qt.resolvedUrl("views/AboutView.qml")
    ]

    property var windowInstance: null

    Component.onCompleted: {
        if (typeof ConfigManager === "undefined" || !ConfigManager) {
            Fluent.Translator.setLanguage(Fluent.Enums.lang.zh_CN)
        }
        windowInstance = windowComponent.createObject(null)
        if (windowInstance) {
            windowInstance.show()
        }
    }
    Component.onDestruction: { if (windowInstance) windowInstance.destroy() }

    property Component windowComponent: Component {
        Fluent.Windows {
            id: appWindow
            width: root.windowWidth; height: root.windowHeight
            visible: false
            minimumWidth: 760
            minimumHeight: 560
            windowTitle: root.windowTitle
            windowIcon: typeof AppLogo !== "undefined" ? AppLogo : ""
            windowIconColored: true
            navigationItems: root.navItems
            bottomNavigationItems: root.bottomNavItems
            pageSources: root.pagePaths
            micaEnabled: typeof ConfigManager !== "undefined" && ConfigManager
                         ? ConfigManager.micaEnabled : false
            lazyLoading: true
            splashIcon: typeof AppLogo !== "undefined" ? AppLogo : ""
            splashTitle: root.windowTitle
            splashSubtitle: "正在加载..."

            property Component updateProgressPresenter: Component {
                id: updateProgressPresenter
                Fluent.AutoUpdaterProgressDialogPresenter {}
            }

            property QtObject autoUpdater: Fluent.AutoUpdater {
                id: autoUpdater
                objectName: "configPilotAutoUpdater"
                updater: appUpdater
                autoDownload: true
                silentArgs: AppInstallerSilentArgs
                notifyWhenUpToDate: false
                feedbackPresenter: updateProgressPresenter
            }

            // PrismQML 0.4+ 自动创建并管理 splashComponent；业务只配置外观。
            Component.onCompleted: {
                if (AppAutoCheckEnabled) updateCheckTimer.start()
            }

            property Item updateLayer: Item {
                id: updateLayer
                anchors.fill: parent
                z: 10000

                Timer {
                    id: updateCheckTimer
                    interval: AppUpdateStartupDelayMs
                    repeat: false
                    onTriggered: autoUpdater.checkSilently()
                }
            }

            // ==================== 关闭主窗口：先问，不静默缩托盘 ====================
            // 关窗必须走引擎的「已接受关闭」链路才有关闭动画：
            // WindowsCore.requestClose() 会先置 closeRequestAccepted=true、把
            // closeRequestHideOnly 复位成 false，再发 closeRequested() 让这里决定；
            // 只要这里不把 closeRequestAccepted 改回 false，引擎就会调
            // _startAcceptedClose() → closeTransition.collapse() 播圆形收紧动画，
            // 动画播完才 hide()（hideOnly）或真正 close()（退出）。
            // 以前这里在拦截关窗后直接 hide()/Qt.quit()，等于永远绕开
            // _startAcceptedClose()，所以关闭时一点动画都没有。别再直接调
            // hide()/Qt.quit()：那样动画不会播。
            //
            // quitApproved 用来放行退出时系统补发的第二次关闭请求（否则 Qt.quit()
            // 之后窗口还会再问一遍）。closeRequestAccepted 保持 true 就是「这一次
            // 交给引擎带动画地走完」。
            property bool quitApproved: false
            // 一次性决定通道：用户在弹窗里点完，进入 beginAnimatedClose() 时先写上
            // "tray"/"quit"，requestClose() 同步发出 closeRequested() 期间被这里读走，
            // 函数返回后立刻清空。用「同步消费」而不是常驻标志，避免下一次点 ✕ 被
            // 上一次的决定误伤。
            property string closeDecision: ""

            // 已记住的关闭方式（"ask"/"tray"/"quit"）。由 CloseBehaviorStore 提供；
            // 它在 Python 侧没注册时按 "ask" 处理，行为与重做前一致。
            readonly property var closeBehaviorStore:
                typeof CloseBehavior !== "undefined" ? CloseBehavior : null
            readonly property string closeBehavior:
                closeBehaviorStore ? closeBehaviorStore.closeBehavior : "ask"

            // 把「勾选记住」的选择落盘。没注册 store 时静默跳过，
            // 不能让未注册的场景在点退出时抛 ReferenceError。
            function rememberCloseChoice() {
                if (!closeBehaviorStore) return
                var behavior = closeChoiceDialog.rememberedBehavior
                if (behavior !== "") closeBehaviorStore.setBehavior(behavior)
            }

            // 让引擎带着关闭动画走完一次关闭。
            // action="tray" → 收紧动画结束后 hide()；"quit" → 动画结束后真正关窗退出。
            function beginAnimatedClose(action) {
                closeDecision = action
                // requestClose() 内部是同步的：它会立刻发 closeRequested()，由下面
                // 的 onCloseRequested 读走 closeDecision 并设置 hideOnly / quitApproved。
                appWindow.requestClose()
                closeDecision = ""
            }

            onCloseRequested: {
                // 用户刚在弹窗里做出的决定（同步消费）。
                if (appWindow.closeDecision === "tray") {
                    closeRequestHideOnly = true
                    closeRequestAccepted = true
                    return
                }
                if (appWindow.closeDecision === "quit") {
                    appWindow.quitApproved = true
                    closeRequestAccepted = true
                    return
                }

                // 退出已获批准：放行这次（系统补发的）关闭请求。
                if (appWindow.quitApproved) {
                    closeRequestAccepted = true
                    return
                }

                // 勾过「记住我的选择」就照做，不再弹窗，但仍走动画。
                if (appWindow.closeBehavior === "tray") {
                    closeRequestHideOnly = true
                    closeRequestAccepted = true
                    return
                }
                if (appWindow.closeBehavior === "quit") {
                    appWindow.quitApproved = true
                    closeRequestAccepted = true
                    return
                }

                // 每次询问：挡下这次关闭，把窗口原样留着并弹三选一。
                closeRequestAccepted = false
                if (!closeChoiceDialog.isOpen) closeChoiceDialog.open()
            }

            // 退出这条路要等动画播完、窗口真的关掉之后再退进程。
            // 隐藏式关闭不会走到这里（它只 hide()，不调 close()）。
            onNativeCloseAccepted: {
                if (appWindow.quitApproved) Qt.callLater(Qt.quit)
            }

            CloseChoiceDialog {
                id: closeChoiceDialog

                // Fluent.Windows 的默认属性是 pages（页面列表），不是 contentData。
                // 声明在这里的对话框因此拿不到视觉父项：parent=null、尺寸 0x0，
                // open() 只把 _isOpen 置真，Window.window 解析不出来 → 永远不可见。
                // 结果就是点标题栏关闭后窗口被 closeRequestAccepted=false 留下，
                // 确认框却根本没出现，看起来「关不掉」。显式挂到窗口 contentItem，
                // 走 OverlayDialogCore 的窗口级覆盖，和页面里声明的对话框同一层级。
                parent: appWindow.contentItem

                onQuitRequested: {
                    appWindow.rememberCloseChoice()
                    // 先把记住的选择落盘，再交给引擎带动画地关窗退出。
                    appWindow.beginAnimatedClose("quit")
                }
                // 缩到托盘只是隐藏窗口：桌宠由 PetManager 跟着主窗口一起隐藏，
                // 托盘菜单「显示主界面」再把它叫回来。
                // 仍然先播关闭动画（hideOnly），动画结束才真正 hide()。
                onTrayRequested: {
                    appWindow.rememberCloseChoice()
                    appWindow.beginAnimatedClose("tray")
                }
            }
        }
    }

}
