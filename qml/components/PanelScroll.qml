import QtQuick
import PrismQML as Fluent

Fluent.ScrollArea {
    id: root

    property int contentPadding: Fluent.Enums.spacing.s
    default property alias panelContent: contentColumn.data
    readonly property real contentWidth: Math.max(
        0, contentColumn.width - contentColumn.leftPadding
           - contentColumn.rightPadding
    )

    Column {
        id: contentColumn

        width: parent ? parent.width : 0
        leftPadding: root.contentPadding
        rightPadding: root.contentPadding
        topPadding: root.contentPadding
        bottomPadding: root.contentPadding
        spacing: Fluent.Enums.spacing.m
    }
}
