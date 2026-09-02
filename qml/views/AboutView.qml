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
    readonly property string appAuthor:
        typeof AppAuthor !== "undefined" ? AppAuthor : ""
    readonly property int appYear:
        typeof AppYear !== "undefined" ? AppYear : 0
    readonly property url appHomepage:
        typeof AppHomepage !== "undefined" ? AppHomepage : ""
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
                            text: "设置"
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
                              ? "v" + root.appVersion : "设置"
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

                    Item {
                        id: aboutCardHost
                        objectName: "aboutSettingsCard"
                        width: parent ? parent.width : 0
                        implicitHeight: Fluent.Enums.settingCard.height_with_content
                        height: implicitHeight

                        Fluent.SettingsCardCore {
                            id: aboutCard
                            anchors.fill: parent
                            title: ""
                            icon: Fluent.Enums.icon.info
                            content: " "
                        }

                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: Fluent.Enums.spacing.xl
                                                + Fluent.Enums.settingCard.icon_size
                                                + Fluent.Enums.spacing.xl
                            anchors.right: checkUpdateButton.left
                            anchors.rightMargin: Fluent.Enums.spacing.xl
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Fluent.Enums.spacing.none
                            z: 1

                            Row {
                                spacing: Fluent.Enums.spacing.xxs

                                Fluent.Label {
                                    objectName: "aboutTitleLabel"
                                    type: Fluent.Enums.label.type_body_strong
                                    text: "关于"
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Fluent.Label {
                                    objectName: "projectHomepageLink"
                                    type: Fluent.Enums.label.type_hyperlink
                                    text: "ConfigPilot"
                                    url: root.appHomepage
                                    // 标题行超链接保持与"关于"同一字重，避免视觉降级。
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.NoWrap
                                    elide: Text.ElideRight
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            Row {
                                spacing: Fluent.Enums.spacing.xxs

                                Fluent.Label {
                                    objectName: "aboutVersionPrefix"
                                    type: Fluent.Enums.label.type_body_small
                                    text: "版本 " + root.appVersion
                                          + " · © " + root.appYear + " "
                                          + root.appAuthor + " · 基于"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Fluent.Label {
                                    objectName: "prismQmlHomepageLink"
                                    type: Fluent.Enums.label.type_hyperlink
                                    text: "PrismQML"
                                    url: root.prismQmlHomepage
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Fluent.Label {
                                    objectName: "aboutDescriptionSuffix"
                                    type: Fluent.Enums.label.type_body_small
                                    text: "引擎构建。"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        Fluent.Button {
                            id: checkUpdateButton
                            objectName: "updateSettingsCard"
                            anchors.right: parent.right
                            anchors.rightMargin: Fluent.Enums.spacing.xl
                            anchors.verticalCenter: parent.verticalCenter
                            text: autoUpdater.feedbackModel.checking
                                  ? "正在检查..." : "检查更新"
                            style: Fluent.Enums.button.style_default
                            enabled: !autoUpdater.feedbackModel.checking
                            onClicked: autoUpdater.check()
                            z: 1
                        }
                    }
                }
            }
        }
    }
}
