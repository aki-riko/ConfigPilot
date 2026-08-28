// 统一页面脚手架:滚动、最大内容宽度和页面边距。
import QtQuick
import QtQuick.Layouts

import PrismQML as Fluent

Fluent.ScrollArea {
    id: scaffold

    property int maxContentWidth: 960
    default property alias pageContent: contentColumn.data
    readonly property real contentWidth: contentColumn.width

    Item {
        width: scaffold.width
        implicitHeight: contentColumn.implicitHeight + Fluent.Enums.spacing.xxl * 2

        ColumnLayout {
            id: contentColumn
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: Fluent.Enums.spacing.xxl
            width: Math.min(
                scaffold.width - Fluent.Enums.spacing.xxl * 2,
                scaffold.maxContentWidth
            )
            spacing: Fluent.Enums.spacing.l
        }
    }
}
