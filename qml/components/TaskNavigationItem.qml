import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Rectangle {
    id: root

    required property int index
    required property var modelData
    property string title: ""
    property string subtitle: ""
    property string icon: ""
    property bool selected: false
    property bool compact: false
    readonly property bool hovered: pointerArea.containsMouse

    signal clicked()

    readonly property int compactWidth: Fluent.Enums.controlSize.navPanelItemWidth * 2
                                        + Fluent.Enums.spacing.s
    readonly property int expandedWidth: Fluent.Enums.window.navPanelMinWidth
                                         - Fluent.Enums.spacing.xl
    readonly property int compactHeight: Fluent.Enums.controlSize.navBarHeight
                                         - Fluent.Enums.spacing.xs
    readonly property int expandedHeight: Fluent.Enums.controlSize.navPanelItemHeight
                                          + Fluent.Enums.spacing.xxs

    implicitWidth: compact ? compactWidth : expandedWidth
    implicitHeight: compact ? compactHeight : expandedHeight
    color: selected
           ? (hovered
              ? Fluent.Enums.stateColor.selectedHover
              : Fluent.Enums.stateColor.selected)
           : (hovered
              ? Fluent.Enums.stateColor.hover
              : Fluent.Enums.transparent)
    radius: Fluent.Enums.radius.small

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Fluent.Enums.spacing.m
        anchors.rightMargin: Fluent.Enums.spacing.m
        spacing: Fluent.Enums.spacing.s

        Fluent.Icon {
            Layout.alignment: Qt.AlignVCenter
            icon: root.icon
            iconSize: Fluent.Enums.iconSize.m
            color: root.selected
                   ? Fluent.Enums.accentColor
                   : Fluent.Enums.textColor.secondary
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignVCenter
            spacing: Fluent.Enums.spacing.micro

            Text {
                Layout.fillWidth: true
                text: root.title
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.bodySmall
                font.bold: root.selected
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
                horizontalAlignment: root.compact
                                     ? Text.AlignHCenter
                                     : Text.AlignLeft
            }

            Text {
                Layout.fillWidth: true
                visible: !root.compact && root.subtitle.length > 0
                text: root.subtitle
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: Fluent.Enums.spacing.s
        anchors.bottomMargin: Fluent.Enums.spacing.s
        width: Fluent.Enums.spacing.xxs + Fluent.Enums.spacing.micro
        visible: root.selected && !root.compact
        color: Fluent.Enums.accentColor
        radius: Fluent.Enums.radius.small
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: Fluent.Enums.spacing.m
        anchors.rightMargin: Fluent.Enums.spacing.m
        height: Fluent.Enums.spacing.xxs + Fluent.Enums.spacing.micro
        visible: root.selected && root.compact
        color: Fluent.Enums.accentColor
        radius: Fluent.Enums.radius.small
    }

    MouseArea {
        id: pointerArea

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
