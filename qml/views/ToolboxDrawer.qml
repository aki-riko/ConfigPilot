import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

// 工具箱：把维护类操作收进一个外抽屉（mode_outside，从宿主窗口外侧滑出），
// 不再让六个按钮横铺在设置页里。抽屉内容全是"低频、有副作用"的操作，
// 因此每项都带一句说明，避免误点。
Fluent.Drawer {
    id: root

    objectName: "codexToolboxDrawer"
    // 外抽屉：贴着主窗口外侧滑出，不遮住页面内容。
    mode: Fluent.Enums.drawer.mode_outside
    position: Fluent.Enums.position.right
    drawerWidth: 360
    drawerHeight: 420
    animationDuration: Fluent.Enums.duration.medium

    property bool configBusy: false
    property bool hasRestorableChanges: false
    // 启动即展开：外抽屉要求宿主窗口已就绪，因此等窗口可见后再开一次。
    // 只自动展开一次，用户手动收起后不再弹回来。
    property bool autoOpened: false

    signal repairRelayAuthRequested()
    signal sandboxStopgapRequested()
    signal restoreInitialRequested()
    signal repairSubagentDefaultsRequested()
    signal reloadRequested()

    function openOnceReady() {
        if (autoOpened) return
        var host = root.Window.window
        if (!host || !host.contentItem) return
        autoOpened = true
        root.open()
    }

    Component.onCompleted: Qt.callLater(openOnceReady)

    // 宿主窗口首帧可见后再补一次：外抽屉要跟随宿主 HWND，太早开会拿不到宿主。
    Timer {
        id: hostReadyTimer
        interval: 120
        repeat: true
        running: !root.autoOpened
        onTriggered: {
            root.openOnceReady()
            if (root.autoOpened) stop()
        }
    }

    // 注意：Drawer 的 contentItem 已经 anchors.fill + margins(spacing.xl)，
    // 内容必须填满它（anchors.fill），不能再自己按 drawerWidth 定宽——那样会
    // 多算一份边距，把右侧的「执行」按钮挤出面板边界。
    ColumnLayout {
        id: contentColumn
        anchors.fill: parent
        spacing: Fluent.Enums.spacing.m

            Text {
                Layout.fillWidth: true
                text: "维护工具箱"
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.bodyLarge
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }

            Text {
                Layout.fillWidth: true
                text: "这些操作会直接改动 Codex 配置，请确认后再执行。"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }

            Fluent.Separator {
                Layout.fillWidth: true
            }

            ToolRow {
                Layout.fillWidth: true
                title: "修复中转站 401"
                description: "用当前填写的密钥重写中转站认证来源"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                onTriggered: root.repairRelayAuthRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "沙盒止血（临时）"
                description: "反复弹出「无法检查 Windows 设置」时写入非沙盒档"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                onTriggered: root.sandboxStopgapRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "修复降智"
                description: "写入稳定的子代理默认模型与推理强度"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                onTriggered: root.repairSubagentDefaultsRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "恢复初始设置"
                description: root.hasRestorableChanges
                             ? "还原 ConfigPilot 写入且此后未被外部修改的设置"
                             : "当前没有可恢复的修改记录"
                icon: Fluent.Enums.icon.arrow_reset
                busy: root.configBusy
                enabled: !root.configBusy && root.hasRestorableChanges
                onTriggered: root.restoreInitialRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "重新读取"
                description: "丢弃界面草稿，按磁盘上的 config.toml 重新载入"
                icon: Fluent.Enums.icon.arrow_sync
                busy: root.configBusy
                onTriggered: root.reloadRequested()
            }

            Item { Layout.fillHeight: true }
    }

    // 抽屉内单条操作：左侧标题+说明，右侧按钮。整体可点，也保留独立按钮语义。
    component ToolRow: RowLayout {
        id: toolRow
        property string title: ""
        property string description: ""
        property string icon: ""
        property bool busy: false
        signal triggered()

        spacing: Fluent.Enums.spacing.m

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Fluent.Enums.spacing.xxs

            Text {
                Layout.fillWidth: true
                text: toolRow.title
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.body
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: toolRow.description
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
        }

        Fluent.Button {
            Layout.minimumWidth: 88
            Layout.preferredWidth: 88
            Layout.maximumWidth: 88
            style: Fluent.Enums.button.style_default
            icon: toolRow.icon
            text: toolRow.busy ? "处理中..." : "执行"
            enabled: toolRow.enabled && !toolRow.busy
            onClicked: toolRow.triggered()
        }
    }
}
