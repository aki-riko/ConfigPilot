// 明细面板里的数据小卡:上面一行说明,下面一行数值。
// 外壳直接用框架的 Fluent.Card(皮肤感知的边框/底色/悬停),配色走 Enums 令牌。
import QtQuick

import PrismQML as Fluent

Fluent.Card {
    id: card

    property string caption: ""
    property string value: ""
    property bool highlight: false
    property bool danger: false

    contentPadding: 0
    height: 52

    Text {
        id: captionLabel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 8
        text: card.caption
        font.pixelSize: 10
        color: Fluent.Enums.tertiaryForeground
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
               ? Fluent.Enums.statusLevel.errorColor
               : (card.highlight ? Fluent.Enums.accentColor
                                 : Fluent.Enums.foregroundColor)
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
    }
}
