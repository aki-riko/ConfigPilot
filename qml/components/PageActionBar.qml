import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Rectangle {
    id: root

    property string statusText: ""
    property color statusColor: Fluent.Enums.textColor.tertiary
    property int horizontalPadding: Fluent.Enums.spacing.xl
    default property alias actions: actionRow.data

    implicitHeight: Fluent.Enums.controlSize.buttonHeight
                    + Fluent.Enums.spacing.l * 2
    color: Fluent.Enums.stateColor.controlBg

    Fluent.Separator {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: root.horizontalPadding
        anchors.rightMargin: root.horizontalPadding
        spacing: Fluent.Enums.spacing.m

        Rectangle {
            Layout.preferredWidth: Fluent.Enums.spacing.s
            Layout.preferredHeight: Fluent.Enums.spacing.s
            Layout.alignment: Qt.AlignVCenter
            visible: root.statusText.length > 0
            color: root.statusColor
            radius: width / 2
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.statusText
            color: root.statusColor
            font.pixelSize: Fluent.Enums.typography.bodySmall
            font.family: Fluent.Enums.fontFamily
            elide: Text.ElideRight
        }

        RowLayout {
            id: actionRow

            Layout.alignment: Qt.AlignVCenter
            spacing: Fluent.Enums.spacing.s
        }
    }
}
