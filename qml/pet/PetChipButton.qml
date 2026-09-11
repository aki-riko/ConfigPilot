// 桌宠明细面板头部的小胶囊按钮(刷新 / 收起)。
// 颜色通过属性注入,便于与悬浮窗的统一配色保持一致。
import QtQuick

Rectangle {
    id: button

    property string label: ""
    property bool emphasized: false
    property color idleColor: "#F2F4F9"
    property color hoverColor: "#EEF1F8"
    property color pressedColor: "#E3E7F1"
    property color emphasizedIdleColor: "#EDF2FF"
    property color emphasizedHoverColor: "#E4ECFF"
    property color emphasizedPressedColor: "#D4E0FF"
    property color normalTextColor: "#5B6478"
    property color emphasizedTextColor: "#3E5BD8"
    property int fontSize: 11

    signal activated()

    width: labelLabel.implicitWidth + 20
    height: 22
    radius: 11
    color: {
        if (area.pressed) return button.emphasized ? button.emphasizedPressedColor : button.pressedColor
        if (area.containsMouse) return button.emphasized ? button.emphasizedHoverColor : button.hoverColor
        return button.emphasized ? button.emphasizedIdleColor : button.idleColor
    }

    Text {
        id: labelLabel
        anchors.centerIn: parent
        text: button.label
        font.pixelSize: button.fontSize
        color: button.emphasized ? button.emphasizedTextColor : button.normalTextColor
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: button.activated()
    }
}
