import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

pragma ComponentBehavior: Bound

Item {
    id: root

    property var model: []
    property int currentIndex: 0
    property bool compact: false

    signal activated(int index)

    implicitWidth: compact ? 0 : (Fluent.Enums.window.navPanelMinWidth
                                  - Fluent.Enums.spacing.xl)
    implicitHeight: compact
                    ? Fluent.Enums.controlSize.navBarHeight
                      - Fluent.Enums.spacing.xs
                    : verticalItems.implicitHeight

    RowLayout {
        id: horizontalItems

        anchors.fill: parent
        visible: root.compact
        spacing: Fluent.Enums.spacing.xs

        Repeater {
            model: root.model

            delegate: TaskNavigationItem {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                title: modelData.title || ""
                subtitle: modelData.subtitle || ""
                icon: modelData.icon || ""
                selected: index === root.currentIndex
                compact: true
                onClicked: root.activated(index)
            }
        }
    }

    Column {
        id: verticalItems

        width: parent.width
        visible: !root.compact
        spacing: Fluent.Enums.spacing.xs

        Repeater {
            model: root.model

            delegate: TaskNavigationItem {
                width: verticalItems.width
                title: modelData.title || ""
                subtitle: modelData.subtitle || ""
                icon: modelData.icon || ""
                selected: index === root.currentIndex
                compact: false
                onClicked: root.activated(index)
            }
        }
    }
}
