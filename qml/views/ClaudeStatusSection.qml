import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property bool installed: false
    property bool developerModeEnabled: false
    property bool thirdPartyEnabled: false
    property bool gatewayCanEnable: false
    property bool configBusy: false
    property bool installBusy: false
    property bool installCancelable: false
    property int installProgress: -1
    property string installStatus: ""
    property string profileName: ""
    property string configPath: ""
    property bool configPilotProfileExists: false
    property string activeProfileName: ""
    property bool canImportActiveProfile: false
    readonly property var installOptions: [
        { "text": "Claude Code CLI", "id": "claude-code" },
        { "text": "Claude Desktop 官网版", "id": "claude-desktop" }
    ]

    signal developerModeToggled(bool value)
    signal gatewayToggled(bool value)
    signal installRequested(string product)
    signal cancelInstallRequested()
    signal cloneActiveProfileRequested()

    title: "应用状态"
    content: ""
    icon: Fluent.Enums.icon.desktop
    expanded: false
    contentPadding: 0

    headerContent: Component {
        Fluent.Badge {
            text: root.installed ? "已安装" : "未安装"
            level: root.installed
                   ? Fluent.Enums.statusLevel.success
                   : Fluent.Enums.statusLevel.attention
        }
    }

    // 高度用 implicitHeight（含 padding）；childrenRect 不含 padding 会裁掉底部。
    Item {
        width: parent ? parent.width : 0
        implicitHeight: cardColumn.implicitHeight
        height: implicitHeight

        Column {
            id: cardColumn
            objectName: "claudeStatusCardColumn"
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            GridLayout {
                id: summaryLayout
                width: cardColumn.innerWidth
                columns: width < 700 ? 1 : 2
                columnSpacing: Fluent.Enums.spacing.l
                rowSpacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: 240
                Layout.maximumWidth: 240
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Claude Desktop"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.installed ? "已安装" : "未检测到安装"
                    visible: false
                    level: root.installed
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.warning
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.Button {
                        objectName: "claudeInstallDropdown"
                        Layout.minimumWidth: 180
                        Layout.preferredWidth: 180
                        Layout.maximumWidth: 180
                        enabled: !root.installBusy
                        style: Fluent.Enums.button.style_default
                        feature: Fluent.Enums.button.feature_dropdown
                        icon: Fluent.Enums.icon.arrow_download
                        text: root.installed ? "安装/更新" : "获取 Claude"
                        menuItems: root.installOptions
                        onMenuItemClicked: function(index, text) {
                            if (index >= 0 && index < root.installOptions.length) {
                                root.installRequested(root.installOptions[index].id)
                            }
                        }
                    }

                    Fluent.Button {
                        Layout.minimumWidth: 72
                        Layout.preferredWidth: 72
                        Layout.maximumWidth: 72
                        visible: root.installBusy
                        enabled: root.installCancelable
                        style: Fluent.Enums.button.style_default
                        icon: Fluent.Enums.icon.dismiss
                        text: "取消"
                        onClicked: root.cancelInstallRequested()
                    }
                }
                Fluent.ProgressBar {
                    Layout.fillWidth: true
                    visible: root.installBusy
                    from: 0
                    to: 100
                    value: Math.max(0, root.installProgress)
                    indeterminate: root.installProgress < 0
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.installStatus.length > 0
                    text: root.installStatus
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            // 状态卡片也单列纵向排列：标题在上、控件在下，与其它字段同一套行序。
            // 之前三个状态并排三列，标题居中、宽度等分，窄窗口下会挤成一团。
            ColumnLayout {
                id: statusGrid
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.m

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        text: "开发者模式"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Toggle {
                        id: developerModeToggle
                        objectName: "claudeDeveloperModeToggle"
                        controlType: Fluent.Enums.toggle.control_switch
                        type: Fluent.Enums.toggle.type_default
                        enabled: !root.configBusy
                        text: root.developerModeEnabled ? "已启用" : "未启用"

                        function syncChecked() {
                            if (checked !== root.developerModeEnabled) {
                                checked = root.developerModeEnabled
                            }
                        }

                        Component.onCompleted: Qt.callLater(syncChecked)
                        onToggled: function(checkedValue) {
                            root.developerModeToggled(checkedValue)
                            Qt.callLater(syncChecked)
                        }
                        Connections {
                            target: root
                            function onDeveloperModeEnabledChanged() {
                                developerModeToggle.syncChecked()
                            }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        text: "推理网关"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Toggle {
                        id: gatewayToggle
                        objectName: "claudeGatewayToggle"
                        enabled: !root.configBusy
                                 && (root.thirdPartyEnabled || root.gatewayCanEnable)
                        controlType: Fluent.Enums.toggle.control_switch
                        type: Fluent.Enums.toggle.type_default
                        text: root.thirdPartyEnabled ? "已应用" : "未启用"

                        function syncChecked() {
                            if (checked !== root.thirdPartyEnabled) {
                                checked = root.thirdPartyEnabled
                            }
                        }

                        Component.onCompleted: Qt.callLater(syncChecked)
                        onToggled: function(checkedValue) {
                            root.gatewayToggled(checkedValue)
                            Qt.callLater(syncChecked)
                        }
                        Connections {
                            target: root
                            function onThirdPartyEnabledChanged() {
                                gatewayToggle.syncChecked()
                            }
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        text: "配置档案"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Badge {
                        text: root.profileName.length > 0 ? root.profileName : "未创建"
                        level: root.profileName.length > 0
                               ? Fluent.Enums.statusLevel.info
                               : Fluent.Enums.statusLevel.attention
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.activeProfileName.length > 0
                                 && root.activeProfileName !== "ConfigPilot"
                        text: "当前 Claude 档案：" + root.activeProfileName + "（只读）"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }
                }
            }

        }

            RowLayout {
                width: parent.width
                visible: root.canImportActiveProfile
                spacing: Fluent.Enums.spacing.m

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        text: "导入当前 Claude 档案"
                        color: Fluent.Enums.textColor.secondary
                        font.pixelSize: Fluent.Enums.typography.body
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "复制为独立的 ConfigPilot 档案，不修改当前档案"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }
                }

                Fluent.Button {
                    objectName: "claudeCloneProfileButton"
                    Layout.minimumWidth: 220
                    Layout.preferredWidth: 220
                    Layout.maximumWidth: 220
                    Layout.alignment: Qt.AlignVCenter
                    enabled: !root.configBusy && !root.installBusy
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.copy
                    text: "复制当前档案为 ConfigPilot"
                    onClicked: root.cloneActiveProfileRequested()
                }
            }
        }
    }
}
