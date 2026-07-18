import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
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
    readonly property var installOptions: [
        { "text": "Claude Code CLI", "id": "claude-code" },
        { "text": "Claude Desktop 官网版", "id": "claude-desktop" }
    ]

    signal developerModeToggled(bool value)
    signal gatewayToggled(bool value)
    signal installRequested(string product)
    signal cancelInstallRequested()

    autoHeight: true

    Column {
        id: cardColumn
        width: parent ? parent.width : 0
        leftPadding: Fluent.Enums.spacing.l
        rightPadding: Fluent.Enums.spacing.l
        topPadding: Fluent.Enums.spacing.m
        bottomPadding: Fluent.Enums.spacing.m

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
                    visible: root.installed
                    level: root.installed
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.warning
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Fluent.Enums.spacing.xs

                    Fluent.Button {
                        objectName: "claudeInstallDropdown"
                        Layout.fillWidth: true
                        enabled: !root.installBusy
                        style: Fluent.Enums.button.style_default
                        feature: Fluent.Enums.button.feature_dropdown
                        text: root.installed ? "安装/更新" : "获取 Claude"
                        menuItems: root.installOptions
                        onMenuItemClicked: function(index, text) {
                            if (index >= 0 && index < root.installOptions.length) {
                                root.installRequested(root.installOptions[index].id)
                            }
                        }
                    }

                    Fluent.Button {
                        visible: root.installBusy
                        enabled: root.installCancelable
                        style: Fluent.Enums.button.style_default
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

            GridLayout {
                id: statusGrid
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: summaryLayout.columns === 2
                                       ? Math.max(
                                             0,
                                             summaryLayout.width - 240
                                             - summaryLayout.columnSpacing
                                         )
                                       : summaryLayout.width
                Layout.alignment: Qt.AlignVCenter
                columns: width < 480 ? 1 : 3
                uniformCellWidths: columns === 3
                columnSpacing: Fluent.Enums.spacing.l
                rowSpacing: Fluent.Enums.spacing.m
                readonly property real equalItemWidth: columns === 3
                                                       ? Math.max(
                                                             0,
                                                             (width
                                                              - 2 * columnSpacing)
                                                             / 3
                                                         )
                                                       : width

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: statusGrid.equalItemWidth
                    Layout.maximumWidth: statusGrid.equalItemWidth
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Developer Mode"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Toggle {
                        id: developerModeToggle
                        objectName: "claudeDeveloperModeToggle"
                        Layout.alignment: Qt.AlignHCenter
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
                    Layout.preferredWidth: statusGrid.equalItemWidth
                    Layout.maximumWidth: statusGrid.equalItemWidth
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Gateway"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Toggle {
                        id: gatewayToggle
                        objectName: "claudeGatewayToggle"
                        Layout.alignment: Qt.AlignHCenter
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
                    Layout.preferredWidth: statusGrid.equalItemWidth
                    Layout.maximumWidth: statusGrid.equalItemWidth
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "配置档案"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.Badge {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.profileName.length > 0 ? root.profileName : "未创建"
                        level: root.profileName.length > 0
                               ? Fluent.Enums.statusLevel.info
                               : Fluent.Enums.statusLevel.attention
                    }
                }
            }
        }
    }
}
