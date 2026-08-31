// 帮助页
import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Item {
    id: root

    readonly property int pagePadding: width < 720
                                       ? Fluent.Enums.spacing.l
                                       : Fluent.Enums.spacing.xl
    readonly property int contentMaxWidth: 920
    readonly property var configManager:
        typeof ConfigManager !== "undefined" ? ConfigManager : null
    readonly property string appVersion:
        typeof AppVersion !== "undefined" ? AppVersion : ""
    readonly property string prismQmlVersion:
        typeof PrismQMLVersion !== "undefined" ? PrismQMLVersion : ""
    readonly property url prismQmlHomepage:
        typeof PrismQMLHomepage !== "undefined" ? PrismQMLHomepage : ""

    // 帮助页复用引擎 updater，由 PrismQML AutoUpdater 负责反馈、下载与安装。
    Component {
        id: progressPresenter
        Fluent.AutoUpdaterProgressDialogPresenter {}
    }

    Fluent.AutoUpdater {
        id: autoUpdater
        updater: appUpdater
        autoDownload: true
        silentArgs: AppInstallerSilentArgs
        notifyWhenUpToDate: true
        feedbackPresenter: progressPresenter
    }

    Fluent.ScrollArea {
        id: scrollArea
        anchors.fill: parent
        padding: Fluent.Enums.spacing.none
        orientation: Qt.Vertical

        Item {
            id: pageFrame
            width: Math.min(
                parent ? parent.width : 0, root.contentMaxWidth
            )
            x: Math.max(
                0, ((parent ? parent.width : 0) - width) / 2
            )
            implicitHeight: pageColumn.implicitHeight
            height: pageColumn.implicitHeight

            Column {
                id: pageColumn
                width: pageFrame.width
                leftPadding: root.pagePadding
                rightPadding: root.pagePadding
                topPadding: Fluent.Enums.spacing.l
                bottomPadding: Fluent.Enums.spacing.xxxl
                spacing: Fluent.Enums.spacing.l

                readonly property real innerWidth: Math.max(
                    0, width - leftPadding - rightPadding
                )

                RowLayout {
                    width: pageColumn.innerWidth
                    spacing: Fluent.Enums.spacing.m

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Fluent.Enums.spacing.xxs

                        Text {
                            text: "帮助"
                            font.pixelSize: Fluent.Enums.typography.display
                            font.bold: true
                            color: Fluent.Enums.textColor.primary
                            font.family: Fluent.Enums.fontFamily
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "基础设置、使用说明与版本信息"
                            font.pixelSize: Fluent.Enums.typography.bodySmall
                            color: Fluent.Enums.textColor.secondary
                            font.family: Fluent.Enums.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    Fluent.Badge {
                        text: root.appVersion.length > 0
                              ? "v" + root.appVersion : "帮助"
                        level: Fluent.Enums.statusLevel.info
                    }
                }

                Rectangle {
                    width: pageColumn.innerWidth
                    height: Fluent.Enums.border.thin
                    color: Fluent.Enums.stateColor.borderLight
                }

                Fluent.SettingsCardGroup {
                    objectName: "basicSettingsGroup"
                    width: pageColumn.innerWidth
                    title: "基础设置"
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.SettingsCard {
                        id: themeSettingsCard
                        objectName: "themeSettingsCard"

                        readonly property var themeValues:
                            root.configManager
                            ? root.configManager.themeOptions : []
                        readonly property int themeIndex:
                            root.configManager
                            ? themeValues.indexOf(root.configManager.theme) : -1

                        width: parent ? parent.width : 0
                        title: "应用主题"
                        content: "跟随系统或固定使用浅色、深色界面"
                        icon: Fluent.Enums.icon.dark_theme
                        type: Fluent.Enums.settingCard.type_combobox
                        model: ["跟随系统", "浅色", "深色"]
                        currentIndex: themeIndex >= 0 ? themeIndex : 0
                        onIndexSelected: function(index) {
                            if (root.configManager
                                    && index >= 0
                                    && index < themeValues.length) {
                                root.configManager.setTheme(themeValues[index])
                            }
                        }
                    }

                    Fluent.SettingsCard {
                        id: skinSettingsCard
                        objectName: "skinSettingsCard"

                        readonly property var skinValues:
                            root.configManager
                            ? root.configManager.skinOptions : []
                        readonly property int skinIndex:
                            root.configManager
                            ? skinValues.indexOf(root.configManager.skin) : -1

                        width: parent ? parent.width : 0
                        title: "应用皮肤"
                        content: "切换 ConfigPilot 的视觉风格"
                        icon: Fluent.Enums.icon.color
                        type: Fluent.Enums.settingCard.type_combobox
                        model: ["流畅设计", "新粗野主义", "复古票据", "新拟态"]
                        currentIndex: skinIndex >= 0 ? skinIndex : 0
                        onIndexSelected: function(index) {
                            if (root.configManager
                                    && index >= 0
                                    && index < skinValues.length) {
                                root.configManager.setSkin(skinValues[index])
                            }
                        }
                    }

                    Fluent.SettingsCard {
                        objectName: "micaSettingsCard"
                        width: parent ? parent.width : 0
                        title: "云母效果"
                        content: "为窗口应用半透明材质，仅在支持的 Windows 版本生效"
                        icon: Fluent.Enums.icon.blur
                        type: Fluent.Enums.settingCard.type_switch
                        checked: root.configManager
                                 ? root.configManager.micaEnabled : false
                        onSwitchToggled: function(isChecked) {
                            if (root.configManager) {
                                root.configManager.setMicaEnabled(isChecked)
                            }
                        }
                    }

                    Fluent.SettingsCard {
                        id: languageSettingsCard
                        objectName: "languageSettingsCard"

                        readonly property var languageValues:
                            ["zh_CN", "zh_TW", "en", "auto"]
                        readonly property int languageIndex:
                            root.configManager
                            ? languageValues.indexOf(root.configManager.language) : -1

                        width: parent ? parent.width : 0
                        title: "界面语言"
                        content: "选择 ConfigPilot 的显示语言"
                        icon: Fluent.Enums.icon.local_language
                        type: Fluent.Enums.settingCard.type_combobox
                        model: ["简体中文", "繁體中文", "English", "跟随系统"]
                        currentIndex: languageIndex >= 0 ? languageIndex : 3
                        onIndexSelected: function(index) {
                            if (index >= 0 && index < languageValues.length) {
                                Fluent.Translator.setLanguage(languageValues[index])
                            }
                        }
                    }
                }

                Fluent.SettingsCardGroup {
                    objectName: "aboutSettingsGroup"
                    width: pageColumn.innerWidth
                    title: "关于"
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.Card {
                        objectName: "aboutSettingsCard"
                        width: parent ? parent.width : 0
                        autoHeight: true

                        Column {
                            width: parent ? parent.width : 0
                            leftPadding: Fluent.Enums.spacing.l
                            rightPadding: Fluent.Enums.spacing.l
                            topPadding: Fluent.Enums.spacing.l
                            bottomPadding: Fluent.Enums.spacing.l
                            spacing: Fluent.Enums.spacing.m

                            RowLayout {
                                width: parent.width
                                spacing: Fluent.Enums.spacing.m

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: "ConfigPilot"
                                    font.pixelSize: Fluent.Enums.typography.subtitle
                                    font.bold: true
                                    color: Fluent.Enums.textColor.primary
                                    font.family: Fluent.Enums.fontFamily
                                }

                                Fluent.Badge {
                                    text: root.appVersion.length > 0
                                          ? "v" + root.appVersion : ""
                                    level: Fluent.Enums.statusLevel.info
                                    visible: text.length > 0
                                }
                            }

                            Text {
                                text: "AI 工具配置与自动化中心"
                                font.pixelSize: Fluent.Enums.typography.body
                                color: Fluent.Enums.textColor.secondary
                                font.family: Fluent.Enums.fontFamily
                                wrapMode: Text.WordWrap
                            }

                            RowLayout {
                                width: parent.width
                                spacing: Fluent.Enums.spacing.xxs

                                Text {
                                    text: "版本 " + root.appVersion + " · 基于"
                                    font.pixelSize: Fluent.Enums.typography.caption
                                    color: Fluent.Enums.textColor.secondary
                                    font.family: Fluent.Enums.fontFamily
                                }

                                Fluent.Label {
                                    objectName: "prismQmlHomepageLink"
                                    type: Fluent.Enums.label.type_hyperlink
                                    text: "PrismQML"
                                    url: root.prismQmlHomepage
                                }

                                Text {
                                    text: " · MIT"
                                    font.pixelSize: Fluent.Enums.typography.caption
                                    color: Fluent.Enums.textColor.secondary
                                    font.family: Fluent.Enums.fontFamily
                                }
                            }
                        }
                    }
                }

                Fluent.SettingsCardGroup {
                    objectName: "applicationSettingsGroup"
                    width: pageColumn.innerWidth
                    title: "应用"
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.SettingsCard {
                        objectName: "updateSettingsCard"
                        width: parent ? parent.width : 0
                        title: "检查更新"
                        content: "当前版本 " + root.appVersion
                                + " · 基于 PrismQML " + root.prismQmlVersion
                        icon: Fluent.Enums.icon.arrow_sync
                        type: Fluent.Enums.settingCard.type_push
                        buttonText: autoUpdater.feedbackModel.checking
                                    ? "正在检查..." : "检查更新"
                        enabled: !autoUpdater.feedbackModel.checking
                        onClicked: autoUpdater.check()
                    }
                }
            }
        }
    }
}
