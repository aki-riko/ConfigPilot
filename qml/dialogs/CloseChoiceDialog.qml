// 关闭主窗口时的三选一：退出程序 / 最小化到托盘 / 取消。
//
// 为什么要自己拼 footer：Fluent.ConfirmDialog 只有「确定 + 取消」两个按钮，
// 而这里需要三个出口 —— 少一个就必然有人被误伤：
//   * 只给「退出/取消」，想挂后台的人没处点；
//   * 把「取消」当成「缩到托盘」，按 Esc 就静默进托盘，正是本次要改掉的默认行为。
// 所以本组件只负责问，不碰窗口：选择用 quitRequested / trayRequested 信号发出去，
// 由 main.qml 决定 Qt.quit() 还是 hide()。
import QtQuick
import QtQuick.Layouts

import PrismQML as Fluent

Fluent.ConfirmDialog {
    id: root

    objectName: "closeChoiceDialog"

    // 本次关闭的最终决定；按 Esc 或点遮罩关掉时保持 "cancel"，窗口原样留着。
    property string choice: "cancel"

    signal quitRequested()
    signal trayRequested()

    level: Fluent.Enums.statusLevel.info
    title: "退出 ConfigPilot"
    message: "关闭主窗口不会自动缩进系统托盘，这里问一句。"
             + "\n\n最小化到托盘：程序继续在后台运行，桌宠和托盘图标都还在，"
             + "点托盘图标可重新打开窗口。"
             + "\n退出程序：结束进程，右下角未点的「应用更改」草稿会一起丢弃。"
    messageAlignment: Text.AlignLeft

    footer: Component {
        RowLayout {
            spacing: Fluent.Enums.spacing.s

            Fluent.Button {
                objectName: "closeChoiceQuitButton"
                Layout.minimumWidth: 96
                Layout.preferredWidth: 96
                Layout.maximumWidth: 96
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_primary
                icon: Fluent.Enums.icon.arrow_exit
                text: "退出程序"
                onClicked: {
                    root.choice = "quit"
                    root.accept()
                }
            }

            Fluent.Button {
                objectName: "closeChoiceTrayButton"
                Layout.minimumWidth: 132
                Layout.preferredWidth: 132
                Layout.maximumWidth: 132
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_default
                icon: Fluent.Enums.icon.arrow_minimize
                text: "最小化到托盘"
                onClicked: {
                    root.choice = "tray"
                    root.accept()
                }
            }

            Fluent.Button {
                objectName: "closeChoiceCancelButton"
                Layout.minimumWidth: 72
                Layout.preferredWidth: 72
                Layout.maximumWidth: 72
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
