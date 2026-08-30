import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string detail: ""
    property string icon: ""
    property bool iconThemeAware: true
    property string statusText: ""
    property int statusLevel: Fluent.Enums.statusLevel.info

    implicitHeight: Math.max(iconFrame.height, titleColumn.implicitHeight)

    RowLayout {
        anchors.fill: parent
        spacing: Fluent.Enums.spacing.m

        Rectangle {
            id: iconFrame

            Layout.preferredWidth: Fluent.Enums.controlSize.navBarHeight
                                     - Fluent.Enums.spacing.xs
            Layout.preferredHeight: Fluent.Enums.controlSize.navBarHeight
                                    - Fluent.Enums.spacing.xs
            Layout.alignment: Qt.AlignTop
            color: Fluent.Enums.stateColor.controlBg
            border.width: Fluent.Enums.border.thin
            border.color: Fluent.Enums.stateColor.borderLight
            radius: Fluent.Enums.radius.large

            Image {
                anchors.centerIn: parent
                visible: !root.iconThemeAware
                width: Fluent.Enums.iconSize.xxxl
                height: Fluent.Enums.iconSize.xxxl
                source: root.icon
                sourceSize.width: width
                sourceSize.height: height
                fillMode: Image.PreserveAspectFit
            }

            Fluent.Icon {
                anchors.centerIn: parent
                visible: root.iconThemeAware
                icon: root.icon
                iconSize: Fluent.Enums.iconSize.xxxl
            }
        }

        ColumnLayout {
            id: titleColumn

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.xxs

            Text {
                Layout.fillWidth: true
                text: root.title
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.titleLarge
                font.bold: true
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                visible: root.subtitle.length > 0
                text: root.subtitle
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.bodySmall
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                visible: root.detail.length > 0
                text: root.detail
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideMiddle
            }
        }

        Fluent.Badge {
            Layout.alignment: Qt.AlignTop
            visible: root.statusText.length > 0
            text: root.statusText
            level: root.statusLevel
        }
    }
}
