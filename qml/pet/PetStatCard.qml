// 明细面板里的数据小卡:上面一行说明,下面一行数值。
import QtQuick

Rectangle {
    id: card

    property string caption: ""
    property string value: ""
    property bool highlight: false
    property bool danger: false

    property color surfaceColor: "#FFFFFF"
    property color borderColor: "#DFE5F4"
    property color captionColor: "#98A0B5"
    property color valueColor: "#2B3252"
    property color highlightColor: "#2F66F4"
    property color dangerColor: "#D5484A"

    height: 52
    radius: 12
    color: card.surfaceColor
    border.color: card.borderColor
    border.width: 1

    Text {
        id: captionLabel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 8
        text: card.caption
        font.pixelSize: 10
        color: card.captionColor
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: captionLabel.bottom
        anchors.topMargin: 2
        width: parent.width - 12
        text: card.value
        font.pixelSize: 17
        font.bold: true
        color: card.danger
               ? card.dangerColor
               : (card.highlight ? card.highlightColor : card.valueColor)
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
    }
}
