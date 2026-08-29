// ConfigPilot 主窗口
import QtQuick

import PrismQML as Fluent

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
        { "text": "帮助", "icon": iconPath("Info"), "key": "AboutView" }
    ]

    property var pagePaths: [
        Qt.resolvedUrl("views/CodexView.qml"),
        Qt.resolvedUrl("views/ClaudeDesktopView.qml"),
        Qt.resolvedUrl("views/AboutView.qml")
    ]

    property var windowInstance: null

    Component.onCompleted: {
        Fluent.Translator.setLanguage(Fluent.Enums.lang.zh_CN)
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
        }
    }

}
