// 明细面板里的数据小卡:上面一行说明,下面一行数值。
// 外壳用框架的 Fluent.Card(皮肤感知的边框/底色/内容边距),文字用 Fluent.Label
// (统一字体族与字重),配色走 Enums 令牌,深浅色/皮肤切换自动跟随。
// 尺寸不在这里决定:宽高都由 PetPanel 的固定行高栅格注入。
import QtQuick

import PrismQML as Fluent

Fluent.Card {
    id: card

    property string caption: ""
    property string value: ""
    property bool highlight: false
    property bool danger: false

    // 内边距归零:卡内是两行固定栅格,由下面两个 Label 的锚点控制留白。
    contentPadding: 0

    Fluent.Label {
        id: captionLabel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Fluent.Enums.spacing.m
        text: card.caption
        // Label 只提供字体族/字重/换行策略,字号与颜色仍按桌宠紧凑栅格指定令牌。
        type: Fluent.Enums.label.type_caption
        font.pixelSize: Fluent.Enums.typography.micro
        customTextColor: Fluent.Enums.tertiaryForeground
    }

    Fluent.Label {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: captionLabel.bottom
        anchors.topMargin: Fluent.Enums.spacing.xxs
        width: parent.width - Fluent.Enums.spacing.l
        text: card.value
        type: Fluent.Enums.label.type_body_strong
        font.pixelSize: Fluent.Enums.typography.subtitle
        customTextColor: card.danger
                         ? Fluent.Enums.statusLevel.errorColor
                         : (card.highlight ? Fluent.Enums.accentColor
                                           : Fluent.Enums.foregroundColor)
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
    }
}
