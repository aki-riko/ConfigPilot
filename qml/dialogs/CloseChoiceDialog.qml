// 关闭主窗口时的三选一：最小化到托盘 / 退出程序 / 取消。
// 组件只负责呈现选择并发出信号，窗口生命周期仍由 main.qml 管理。
//
// 两个出口做成整块可点的选项卡。实现上刻意分层，而不是以前那种
// 「卡片里叠一个 opacity:0 的按钮 + 再盖一层 MouseArea」：
//   1. 以前 MouseArea 在 z:2 盖住按钮，Fluent.Button 自己的 hover 收不到，
//      卡片看着可点却没有任何悬停反馈；
//   2. 隐形按钮仍带 text，读屏会把「最小化到托盘」念两遍。
// 现在是：Rectangle 负责视觉，铺满整块的 Fluent.Button 负责交互
// （悬浮/按下/焦点/Tab/Enter 全走原生），文字图标层压在最上面。
// 卡片本身保留 text / clicked 这套公开契约（按钮不带文字），
// 既让读屏只念一次，也让既有调用方与测试无需改动。
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

    // 勾选「记住我的选择」时为真。真正落盘由 main.qml 通过
    // CloseBehaviorStore 完成（对话框本身不碰持久化，保持只发信号的约定）。
    property bool rememberChoice: false
    // 这次需要被记住的档位（"tray"/"quit"）；取消或没勾选时为空。
    readonly property string rememberedBehavior:
        root.rememberChoice && (choice === "tray" || choice === "quit")
        ? choice : ""

    // 对话框正文宽度：Body 左右各 24px 边距，整体约 568px。
    // 旧版正文只有 464 - 24*2 = 416px，还要再让出右侧「取消」按钮的位置，
    // 副标题正好卡在「操/作。」之间折断。520 是让那行副标题单行放下的下限。
    contentWidth: 520
    actionsVisible: false

    // 注意：这里不重写 open()，也不在关闭时复位 choice。
    // DialogBoxCore 没有 opened 信号（基类只有 accepted/rejected/closed），
    // 而在 closed 里复位会踩到既有契约：accept() 先发 accepted（调用方据此读
    // choice），随后才 close()；在 closed 复位会把调用方刚读到的终值抹掉。
    // 复位属于额外行为变更，本文件只做视觉重做，保持原有行为不变。

    // ==================== Header 标题区 ====================
    ColumnLayout {
        width: 520
        spacing: Fluent.Enums.spacing.l

        RowLayout {
            Layout.fillWidth: true
            spacing: Fluent.Enums.spacing.l

            Rectangle {
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignTop
                radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.large)
                color: Fluent.Enums.withAlpha(
                           root.effectiveSkinContext.accentColor, 0.12)

                Fluent.Icon {
                    anchors.centerIn: parent
                    icon: "Info"
                    iconSize: Fluent.Enums.iconSize.xl
                    color: root.effectiveSkinContext.accentColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Fluent.Label {
                    Layout.fillWidth: true
                    text: "退出 ConfigPilot"
                    type: Fluent.Enums.label.type_subtitle
                    customTextColor: root.effectiveSkinContext.stateColor.textStrong
                }

                Fluent.Label {
                    objectName: "closeChoiceSubtitle"
                    Layout.fillWidth: true
                    text: "关闭主窗口不会自动缩进系统托盘，请选择接下来的操作。"
                    type: Fluent.Enums.label.type_body_small
                    customTextColor: root.effectiveSkinContext.stateColor.textMedium
                    wrapMode: Text.WordWrap
                }
            }

            Fluent.Button {
                objectName: "closeChoiceCancelButton"
                Layout.preferredWidth: 84
                Layout.preferredHeight: Fluent.Enums.dialog.buttonHeight
                Layout.alignment: Qt.AlignTop
                style: Fluent.Enums.button.style_transparent
                icon: "Dismiss"
                text: "取消"
                onClicked: {
                    root.choice = "cancel"
                    root.reject()
                }
            }
        }

        Fluent.Label {
            Layout.fillWidth: true
            text: "选择关闭方式"
            type: Fluent.Enums.label.type_caption
            customTextColor: root.effectiveSkinContext.textColor.tertiary
        }

        // ==================== Choices 选择项 ====================
        // 对外契约保持不变：objectName 在本项上，text 是可见标题，
        // clicked 由内部按钮触发（函数式信号，外部 emit 同样会走到 on 处理）。
        component ChoiceCard: Item {
            id: card

            property string text: ""
            property string description: ""
            property string iconName: ""
            property color iconColor: Fluent.Enums.transparent

            signal clicked()

            Layout.fillWidth: true
            Layout.preferredHeight: 84

            readonly property var skin: root.effectiveSkinContext

            Rectangle {
                id: face
                anchors.fill: parent
                radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.medium)
                color: button.hovered && button.enabled
                       ? card.skin.stateColor.controlBgHover
                       : card.skin.stateColor.controlBg
                border.width: Fluent.Enums.surfaceBorderWidth(
                                  Fluent.Enums.border.thin)
                border.color: button.activeFocus
                              ? card.skin.accentColor
                              : card.skin.stateColor.cardBorder

                Behavior on color {
                    ColorAnimation { duration: Fluent.Enums.duration.fast }
                }
            }

            // 交互层：铺满整卡的原生按钮，但面色全透明，视觉交给上面的 face。
            Fluent.Button {
                id: button
                objectName: card.objectName + "Interaction"
                anchors.fill: parent
                style: Fluent.Enums.button.style_transparent
                radius: Fluent.Enums.surfaceRadius(Fluent.Enums.radius.medium)
                hoverBgColor: Fluent.Enums.transparent
                pressedBgColor: Fluent.Enums.transparent
                activeFocusOnTab: true

                onClicked: card.clicked()
                // Enter / 小键盘 Enter / 空格：Button 自身只处理鼠标点击，
                // 键盘激活必须显式接上，否则 Tab 到卡片后按键毫无反应。
                Keys.onReturnPressed: card.clicked()
                Keys.onEnterPressed: card.clicked()
                Keys.onSpacePressed: card.clicked()
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Fluent.Enums.spacing.xl
                anchors.rightMargin: Fluent.Enums.spacing.xl
                spacing: Fluent.Enums.spacing.l

                // 图标槽固定 28x28：两个选项的文字左缘因此严格对齐。
                // 旧版 Icon 直接进 RowLayout，宽度随字形不同（28 vs 18），
                // 两张卡的文字左缘差了 8px。
                Item {
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    Layout.alignment: Qt.AlignVCenter

                    Fluent.Icon {
                        anchors.centerIn: parent
                        icon: card.iconName
                        iconSize: Fluent.Enums.iconSize.xl
                        color: card.iconColor
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Fluent.Enums.spacing.xxs

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: card.text
                        type: Fluent.Enums.label.type_body_strong
                        customTextColor: card.skin.stateColor.textStrong
                    }

                    Fluent.Label {
                        Layout.fillWidth: true
                        text: card.description
                        type: Fluent.Enums.label.type_caption
                        customTextColor: card.skin.stateColor.textMedium
                        wrapMode: Text.WordWrap
                    }
                }

                Fluent.Icon {
                    Layout.alignment: Qt.AlignVCenter
                    icon: "ChevronRight"
                    iconSize: Fluent.Enums.iconSize.s
                    color: card.skin.textColor.tertiary
                    opacity: button.hovered || button.activeFocus ? 1 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: Fluent.Enums.duration.fast }
                    }
                }
            }
        }

        ChoiceCard {
            objectName: "closeChoiceTrayButton"
            text: "最小化到托盘"
            description: "程序继续在后台运行，点托盘图标可重新打开窗口。"
            iconName: "ArrowMinimize"
            iconColor: root.effectiveSkinContext.accentColor
            onClicked: {
                root.choice = "tray"
                root.accept()
            }
        }

        ChoiceCard {
            objectName: "closeChoiceQuitButton"
            text: "退出程序"
            description: "结束进程，右下角未点的「应用更改」草稿会一起丢弃。"
            iconName: "ArrowExit"
            iconColor: Fluent.Enums.statusLevel.errorColor
            onClicked: {
                root.choice = "quit"
                root.accept()
            }
        }

        // ==================== 记住选择 ====================
        // 勾上后把这次的选择写进关闭行为配置，下次点 ✕ 直接照做、不再弹窗。
        // 「取消」不算一种选择：勾着取消仍然什么都不记，避免把自己锁成「问也不问」。
        Fluent.CheckBox {
            objectName: "closeChoiceRememberCheckBox"
            Layout.fillWidth: true
            Layout.topMargin: Fluent.Enums.spacing.xxs
            text: "记住我的选择，下次不再询问"
            checked: root.rememberChoice
            onCheckedChanged: root.rememberChoice = checked
        }

        Fluent.Label {
            Layout.fillWidth: true
            text: "之后可在「设置 → 基础设置 → 关闭按钮行为」改回来。"
            type: Fluent.Enums.label.type_caption
            customTextColor: root.effectiveSkinContext.textColor.tertiary
            visible: root.rememberChoice
            wrapMode: Text.WordWrap
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


