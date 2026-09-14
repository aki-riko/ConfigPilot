// 关闭主窗口时的三选一：退出程序 / 最小化到托盘 / 取消。
// 组件只负责呈现选择并发出信号，窗口生命周期仍由 main.qml 管理。
import QtQuick
import QtQuick.Layouts

import PrismQML as Fluent

Fluent.DialogBoxCore {
    id: root

    objectName: "closeChoiceDialog"

    // 本次关闭的最终决定；按 Esc 或点遮罩关掉时保持 "cancel"。
    property string choice: "cancel"
    // 保留旧组件公开属性，方便调用方和主题检查继续识别该对话框级别。
    property int level: Fluent.Enums.statusLevel.info
    // 与原 ConfirmDialog 保持一致，调用方通过公开别名读取打开状态。
    readonly property bool isOpen: _isOpen

    signal quitRequested()
    signal trayRequested()

    // 让正文拥有稳定的阅读宽度，避免长文案把弹窗撑成过宽的白板。
    contentWidth: 464

    footer: Component {
        RowLayout {
            property var dialog
            spacing: Fluent.Enums.spacing.s

            Fluent.Button {
                objectName: "closeChoiceQuitButton"
                Layout.preferredWidth: 108
                Layout.preferredHeight: Fluent.Enums.dialog.buttonHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_default
                icon: "ArrowExit"
                text: "退出程序"
                level: Fluent.Enums.statusLevel.error
                onClicked: {
                    root.choice = "quit"
                    root.accept()
                }
            }

            Fluent.Button {
                objectName: "closeChoiceTrayButton"
                Layout.preferredWidth: 152
                Layout.preferredHeight: Fluent.Enums.dialog.buttonHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_filled
                icon: "ArrowMinimize"
                text: "最小化到托盘"
                level: Fluent.Enums.statusLevel.info
                onClicked: {
                    root.choice = "tray"
                    root.accept()
                }
            }

            Fluent.Button {
                objectName: "closeChoiceCancelButton"
                Layout.preferredWidth: 76
                Layout.preferredHeight: Fluent.Enums.dialog.buttonHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_default
                text: "取消"
                onClicked: {
                    root.choice = "cancel"
                    root.reject()
                }
            }
        }
    }

    // ==================== Header 标题区 ====================
    ColumnLayout {
        width: 464
        spacing: Fluent.Enums.spacing.l

        RowLayout {
            Layout.fillWidth: true
            spacing: Fluent.Enums.spacing.m

            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                Layout.alignment: Qt.AlignTop
                radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.large)
                color: root.effectiveSkinContext.stateColor.selected

                Fluent.Icon {
                    anchors.centerIn: parent
                    icon: "Info"
                    iconSize: Fluent.Enums.iconSize.m
                    color: root.effectiveSkinContext.accentColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Fluent.Enums.spacing.xs

                Fluent.Label {
                    Layout.fillWidth: true
                    text: "退出 ConfigPilot"
                    type: Fluent.Enums.label.type_subtitle
                    customTextColor: root.effectiveSkinContext.stateColor.textStrong
                }

                Fluent.Label {
                    Layout.fillWidth: true
                    text: "关闭主窗口不会自动缩进系统托盘，请选择接下来的操作。"
                    type: Fluent.Enums.label.type_body_small
                    customTextColor: root.effectiveSkinContext.stateColor.textMedium
                    wrapMode: Text.WordWrap
                }
            }
        }

        Fluent.Label {
            Layout.fillWidth: true
            text: "选择关闭方式"
            type: Fluent.Enums.label.type_caption
            customTextColor: root.effectiveSkinContext.textColor.secondary
        }

        // ==================== Choices 选择项 ====================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.small)
            color: root.effectiveSkinContext.stateColor.controlBg
            border.width: Fluent.Enums.surfaceBorderWidth(Fluent.Enums.border.thin)
            border.color: root.effectiveSkinContext.stateColor.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: Fluent.Enums.spacing.m
                spacing: Fluent.Enums.spacing.m

                Fluent.Icon {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    icon: "ArrowMinimize"
                    iconSize: Fluent.Enums.iconSize.m
                    color: root.effectiveSkinContext.accentColor
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: "最小化到托盘"
                        type: Fluent.Enums.label.type_body_strong
                        customTextColor: root.effectiveSkinContext.stateColor.textStrong
                    }

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: "程序继续在后台运行，点托盘图标可重新打开窗口。"
                        type: Fluent.Enums.label.type_caption
                        customTextColor: root.effectiveSkinContext.stateColor.textMedium
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.small)
            color: root.effectiveSkinContext.stateColor.bgLight
            border.width: Fluent.Enums.surfaceBorderWidth(Fluent.Enums.border.thin)
            border.color: root.effectiveSkinContext.stateColor.borderLight

            RowLayout {
                anchors.fill: parent
                anchors.margins: Fluent.Enums.spacing.m
                spacing: Fluent.Enums.spacing.m

                Fluent.Icon {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    icon: "ArrowExit"
                    iconSize: Fluent.Enums.iconSize.m
                    color: Fluent.Enums.statusLevel.errorColor
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: "退出程序"
                        type: Fluent.Enums.label.type_body_strong
                        customTextColor: root.effectiveSkinContext.stateColor.textStrong
                    }

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: "结束进程，右下角未点的「应用更改」草稿会一起丢弃。"
                        type: Fluent.Enums.label.type_caption
                        customTextColor: root.effectiveSkinContext.stateColor.textMedium
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }

    // accept() 之后才发信号：此时对话框已经关掉，调用方拿到的 choice 是终值。
    onAccepted: {
        if (root.choice === "quit") {
            root.quitRequested()
        } else if (root.choice === "tray") {
            root.trayRequested()
        }
    }

    onRejected: { root.choice = "cancel" }
}
