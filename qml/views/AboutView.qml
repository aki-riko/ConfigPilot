// 帮助与版本页
import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

import "../components"

Item {
    id: root

    readonly property int pagePadding: width < 720
                                       ? Fluent.Enums.spacing.l
                                       : Fluent.Enums.spacing.xl

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

    PageHeader {
        id: pageHeader

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: root.pagePadding
        anchors.rightMargin: root.pagePadding
        anchors.topMargin: Fluent.Enums.spacing.l
        title: "ConfigPilot"
        subtitle: "帮助与版本信息"
        detail: "基于 PrismQML " + PrismQMLVersion + " · MIT"
        icon: Qt.resolvedUrl("../../resources/app_icon_ai.svg")
        iconThemeAware: false
        statusText: "版本 " + AppVersion
        statusLevel: Fluent.Enums.statusLevel.info
    }

    Fluent.ScrollArea {
        id: scrollArea

        objectName: "aboutScrollArea"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: pageHeader.bottom
        anchors.bottom: actionBar.top
        anchors.topMargin: Fluent.Enums.spacing.m

        Column {
            id: contentColumn

            width: parent ? parent.width : 0
            leftPadding: root.pagePadding
            rightPadding: root.pagePadding
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.m

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            GridLayout {
                id: productGrid

                width: contentColumn.innerWidth
                columns: width < 700 ? 1 : 2
                uniformCellWidths: columns === 2
                columnSpacing: Fluent.Enums.spacing.m
                rowSpacing: Fluent.Enums.spacing.m

                Fluent.Card {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    autoHeight: true

                    Column {
                        width: parent ? parent.width : 0
                        spacing: Fluent.Enums.spacing.m

                        RowLayout {
                            width: parent.width
                            spacing: Fluent.Enums.spacing.s

                            Fluent.Icon {
                                Layout.preferredWidth: 24
                                Layout.preferredHeight: 24
                                icon: Qt.resolvedUrl("../../resources/chatgpt.svg")
                                iconSize: 24
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Codex CLI"
                                color: Fluent.Enums.textColor.primary
                                font.pixelSize: Fluent.Enums.typography.subtitle
                                font.bold: true
                                font.family: Fluent.Enums.fontFamily
                            }

                            Fluent.Badge {
                                text: "config.toml"
                                level: Fluent.Enums.statusLevel.info
                            }
                        }

                        Text {
                            width: parent.width
                            text: "连接与认证\n模型与思考等级\n上下文与自动压缩\n兼容性与响应存储"
                            color: Fluent.Enums.textColor.secondary
                            font.pixelSize: Fluent.Enums.typography.bodySmall
                            font.family: Fluent.Enums.fontFamily
                            lineHeight: 1.5
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Fluent.Card {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    autoHeight: true

                    Column {
                        width: parent ? parent.width : 0
                        spacing: Fluent.Enums.spacing.m

                        RowLayout {
                            width: parent.width
                            spacing: Fluent.Enums.spacing.s

                            Image {
                                Layout.preferredWidth: 24
                                Layout.preferredHeight: 24
                                source: Qt.resolvedUrl("../../resources/claude.svg")
                                sourceSize.width: width
                                sourceSize.height: height
                                fillMode: Image.PreserveAspectFit
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Claude Desktop"
                                color: Fluent.Enums.textColor.primary
                                font.pixelSize: Fluent.Enums.typography.subtitle
                                font.bold: true
                                font.family: Fluent.Enums.fontFamily
                            }

                            Fluent.Badge {
                                text: "Third-Party"
                                level: Fluent.Enums.statusLevel.attention
                            }
                        }

                        Text {
                            width: parent.width
                            text: "Developer Mode\n第三方推理网关\n模型发现与 1M 上下文\n认证密钥与额外请求头"
                            color: Fluent.Enums.textColor.secondary
                            font.pixelSize: Fluent.Enums.typography.bodySmall
                            font.family: Fluent.Enums.fontFamily
                            lineHeight: 1.5
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            Fluent.Card {
                width: contentColumn.innerWidth
                autoHeight: true

                Column {
                    width: parent ? parent.width : 0
                    spacing: Fluent.Enums.spacing.l

                    Text {
                        text: "写入与恢复"
                        color: Fluent.Enums.textColor.primary
                        font.pixelSize: Fluent.Enums.typography.subtitle
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }

                    Fluent.Separator {
                        width: parent.width
                    }

                    GridLayout {
                        width: parent.width
                        columns: width < 640 ? 1 : 3
                        uniformCellWidths: columns === 3
                        columnSpacing: Fluent.Enums.spacing.l
                        rowSpacing: Fluent.Enums.spacing.l

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Fluent.Enums.spacing.xs

                            Fluent.Icon {
                                icon: Fluent.Enums.icon.save_copy
                                iconSize: Fluent.Enums.iconSize.m
                                color: Fluent.Enums.accentColor
                            }
                            Text {
                                text: "自动备份"
                                color: Fluent.Enums.textColor.primary
                                font.pixelSize: Fluent.Enums.typography.bodySmall
                                font.bold: true
                                font.family: Fluent.Enums.fontFamily
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "写入前创建 .bak，原文件保持可回退。"
                                color: Fluent.Enums.textColor.tertiary
                                font.pixelSize: Fluent.Enums.typography.caption
                                font.family: Fluent.Enums.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Fluent.Enums.spacing.xs

                            Fluent.Icon {
                                icon: Fluent.Enums.icon.lock_closed_key
                                iconSize: Fluent.Enums.iconSize.m
                                color: Fluent.Enums.accentColor
                            }
                            Text {
                                text: "敏感字段"
                                color: Fluent.Enums.textColor.primary
                                font.pixelSize: Fluent.Enums.typography.bodySmall
                                font.bold: true
                                font.family: Fluent.Enums.fontFamily
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "密钥留空时保留现有值，不在界面回显。"
                                color: Fluent.Enums.textColor.tertiary
                                font.pixelSize: Fluent.Enums.typography.caption
                                font.family: Fluent.Enums.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Fluent.Enums.spacing.xs

                            Fluent.Icon {
                                icon: Fluent.Enums.icon.arrow_sync
                                iconSize: Fluent.Enums.iconSize.m
                                color: Fluent.Enums.accentColor
                            }
                            Text {
                                text: "完全重启"
                                color: Fluent.Enums.textColor.primary
                                font.pixelSize: Fluent.Enums.typography.bodySmall
                                font.bold: true
                                font.family: Fluent.Enums.fontFamily
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "应用后完全退出并重开对应工具。"
                                color: Fluent.Enums.textColor.tertiary
                                font.pixelSize: Fluent.Enums.typography.caption
                                font.family: Fluent.Enums.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
        }
    }

    PageActionBar {
        id: actionBar

        objectName: "aboutActionBar"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: implicitHeight
        horizontalPadding: root.pagePadding
        statusText: "ConfigPilot " + AppVersion + " · PrismQML "
                    + PrismQMLVersion + " · MIT"
        statusColor: Fluent.Enums.textColor.tertiary

        Fluent.Button {
            objectName: "checkForUpdatesButton"
            style: Fluent.Enums.button.style_primary
            icon: Fluent.Enums.icon.arrow_sync
            text: autoUpdater.feedbackModel.checking
                  ? "正在检查..."
                  : "检查更新"
            enabled: !autoUpdater.feedbackModel.checking
            onClicked: autoUpdater.check()
        }
    }
}
