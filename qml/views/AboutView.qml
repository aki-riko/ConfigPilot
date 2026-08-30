// 帮助页
import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Item {
    id: root

    readonly property int pagePadding: width < 720
                                       ? Fluent.Enums.spacing.l
                                       : Fluent.Enums.spacing.xl
    readonly property int contentMaxWidth: 900

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
                spacing: Fluent.Enums.spacing.l
                leftPadding: root.pagePadding
                rightPadding: root.pagePadding
                topPadding: Fluent.Enums.spacing.l
                bottomPadding: Fluent.Enums.spacing.xxxl

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
                            text: "使用说明、版本信息与更新"
                            font.pixelSize: Fluent.Enums.typography.bodySmall
                            color: Fluent.Enums.textColor.secondary
                            font.family: Fluent.Enums.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    Fluent.Badge {
                        text: "v" + AppVersion
                        level: Fluent.Enums.statusLevel.info
                    }
                }

                Rectangle {
                    width: pageColumn.innerWidth
                    height: Fluent.Enums.border.thin
                    color: Fluent.Enums.stateColor.borderLight
                }

                Fluent.Card {
                    width: pageColumn.innerWidth
                    autoHeight: true
                    Column {
                        width: parent ? parent.width : 0
                        leftPadding: Fluent.Enums.spacing.l
                        rightPadding: Fluent.Enums.spacing.l
                        topPadding: Fluent.Enums.spacing.l
                        bottomPadding: Fluent.Enums.spacing.l
                        spacing: Fluent.Enums.spacing.m
                        Text {
                            text: "ConfigPilot 做什么"
                            font.pixelSize: Fluent.Enums.typography.subtitle
                            font.bold: true
                            color: Fluent.Enums.textColor.primary
                            font.family: Fluent.Enums.fontFamily
                        }
                        Text {
                            text: "ConfigPilot 是 AI 工具配置与自动化中心。当前版本同时管理 Codex CLI 与 Claude Desktop 的第三方连接。\n\n• Codex：管理连接、模型、推理和上下文配置\n• Codex：套用统一的 GPT-5.5 稳定上下文并获取模型列表\n• Claude Desktop：一键启用 Developer Mode 与 Third-Party Inference\n• Claude Desktop：配置 Gateway endpoint、认证方式、模型和额外 Header\n• 敏感字段留空默认保留，写入前自动创建 .bak\n• 改完后必须完全退出并重新打开对应应用"
                            font.pixelSize: Fluent.Enums.typography.body
                            color: Fluent.Enums.textColor.secondary
                            font.family: Fluent.Enums.fontFamily
                            wrapMode: Text.WordWrap
                            width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        }
                    }
                }

            Fluent.Card {
                width: pageColumn.innerWidth
                autoHeight: true
                Column {
                    width: parent ? parent.width : 0
                    leftPadding: Fluent.Enums.spacing.l
                    rightPadding: Fluent.Enums.spacing.l
                    topPadding: Fluent.Enums.spacing.l
                    bottomPadding: Fluent.Enums.spacing.l
                    spacing: Fluent.Enums.spacing.s
                    Text {
                        text: "ConfigPilot"
                        font.pixelSize: Fluent.Enums.typography.subtitle
                        font.bold: true
                        color: Fluent.Enums.textColor.primary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        text: "AI 工具配置与自动化中心\nConfigPilot "
                            + AppVersion + "\n基于 PrismQML (prismqml "
                            + PrismQMLVersion + ") · MIT"
                        font.pixelSize: Fluent.Enums.typography.body
                        color: Fluent.Enums.textColor.secondary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Button {
                        width: 112
                        Layout.minimumWidth: 112
                        Layout.preferredWidth: 112
                        Layout.maximumWidth: 112
                        style: Fluent.Enums.button.style_default
                        icon: Fluent.Enums.icon.arrow_sync
                        text: autoUpdater.feedbackModel.checking
                            ? "正在检查..." : "检查更新"
                        enabled: !autoUpdater.feedbackModel.checking
                        onClicked: autoUpdater.check()
                    }
                }
            }
            }
        }
    }
}
