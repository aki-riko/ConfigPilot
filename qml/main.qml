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

    property var navItems: [
        { "text": "配置", "icon": iconPath("Settings") }
    ]

    property var bottomNavItems: [
        { "text": "帮助", "icon": iconPath("Info"), "key": "AboutView" }
    ]

    property var pagePaths: [
        Qt.resolvedUrl("views/CodexView.qml"),
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
            width: root.windowWidth; height: root.windowHeight
            windowTitle: root.windowTitle
            windowIcon: typeof AppLogo !== "undefined" ? AppLogo : ""
            windowIconColored: true
            navigationItems: root.navItems
            bottomNavigationItems: root.bottomNavItems
            pageSources: root.pagePaths
            lazyLoading: true
            // 启动屏:挂到 _splashInstance,内容加载完成后引擎自动 finish()
            Component.onCompleted: {
                this._splashInstance = root.splashComponent.createObject(this.contentItem)
            }
        }
    }

    // 启动屏组件
    property Component splashComponent: Component {
        Fluent.SplashScreen {
            iconSource: typeof AppLogo !== "undefined" ? AppLogo : ""
            title: root.windowTitle
            subtitle: "正在加载..."
            z: 9999
        }
    }
}
