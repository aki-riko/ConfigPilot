// 统一页面标题、说明和状态操作区。
import QtQuick
import QtQuick.Layouts

import PrismQML as Fluent

RowLayout {
    id: header

    property string title: ""
    property string subtitle: ""
    property string details: ""
    default property alias actionsContent: actionsRow.data

    Layout.fillWidth: true
    spacing: Fluent.Enums.spacing.l

    ColumnLayout {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 0

        Text {
            text: header.title
            font.pixelSize: Fluent.Enums.typography.metric
            font.bold: true
            color: Fluent.Enums.textColor.primary
            font.family: Fluent.Enums.fontFamily
            elide: Text.ElideRight
        }
        Text {
            visible: header.subtitle !== ""
            text: header.subtitle
            font.pixelSize: Fluent.Enums.typography.body
            color: Fluent.Enums.textColor.secondary
            font.family: Fluent.Enums.fontFamily
            elide: Text.ElideRight
        }
        Text {
            visible: header.details !== ""
            text: header.details
            font.pixelSize: Fluent.Enums.typography.caption
            color: Fluent.Enums.textColor.tertiary
            font.family: Fluent.Enums.fontFamily
            elide: Text.ElideMiddle
        }
    }

    Item { Layout.fillWidth: true }

    Row {
        id: actionsRow
        Layout.alignment: Qt.AlignVCenter
        spacing: Fluent.Enums.spacing.s
    }
}
