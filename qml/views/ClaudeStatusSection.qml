import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property bool installed: false
    property bool developerModeEnabled: false
    property bool thirdPartyEnabled: false
    property string profileName: ""
    property string configPath: ""

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
            width: cardColumn.innerWidth
            columns: width < 700 ? 2 : 4
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Claude Desktop"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.installed ? "已安装" : "未检测到安装"
                    level: root.installed
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.warning
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Developer Mode"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.developerModeEnabled ? "已启用" : "等待启用"
                    level: root.developerModeEnabled
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.attention
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Gateway"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.thirdPartyEnabled ? "已应用" : "待配置"
                    level: root.thirdPartyEnabled
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.attention
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
            }
        }
    }
}
