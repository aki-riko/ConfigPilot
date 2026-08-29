// 帮助页
import QtQuick
import PrismQML as Fluent

Item {
    id: root

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
        anchors.fill: parent

        Column {
            width: parent ? parent.width : 0
            spacing: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.xxxl

            Text {
                text: "帮助"
                font.pixelSize: Fluent.Enums.typography.displayLarge
                font.bold: true
                color: Fluent.Enums.textColor.primary
                font.family: Fluent.Enums.fontFamily
            }

            Fluent.Card {
                width: parent ? parent.width : 0
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
                width: parent ? parent.width : 0
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
                        style: Fluent.Enums.button.style_default
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
