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
            // WindowsCore 在 closeRequested() 前把 closeRequestAccepted 复位为 true，
            // 这里置 false 就让它走 _cancelCloseRequest()：窗口原样留着，什么都不发生。
            // 真正的退出由对话框的 quitRequested 触发；quitApproved 用来放行退出时
            // 系统补发的第二次关闭请求（否则 Qt.quit() 之后窗口还会再问一遍）。
            property bool quitApproved: false

            onCloseRequested: {
                if (appWindow.quitApproved) {
                    closeRequestAccepted = true
                    return
                }
                closeRequestAccepted = false
                if (!closeChoiceDialog.isOpen) closeChoiceDialog.open()
            }

            CloseChoiceDialog {
                id: closeChoiceDialog
                onQuitRequested: {
                    appWindow.quitApproved = true
                    Qt.quit()
                }
                // 缩到托盘只是隐藏窗口：桌宠由 PetManager 跟着主窗口一起隐藏，
                // 托盘菜单「显示主界面」再把它叫回来。
                onTrayRequested: appWindow.hide()
            }
        }
    }

}
