// "最近调用"单行:时间 / 模型 / Token(已简写) / 消耗金额,四列定宽对齐。
// 中间模型列占满剩余宽度,长模型名自动省略,不会把 Token 列挤变形。
// 文字用框架的 Fluent.Label(统一字体族与字重),底色与字号走 Enums 令牌。
// 行高与列宽是 PetWindow 固定行高栅格的一部分,改动时必须同步 PetWindow 的
// detailContentHeight 推导注释。
import QtQuick
import QtQuick.Layouts

import PrismQML as Fluent

Rectangle {
    id: row

    property string timeText: ""
    property string modelText: ""
    property string tokensText: ""
    property string costText: ""
    property bool striped: false

    // 列宽:时间 / Token / 金额固定,模型列自适应。
    // 金额列旧值 54 装不下 "$0.0361"(隐宽 77,被省略成 "$0.03…"),Token 列
    // 80 对 "+428.6K / +369" 也只剩零点余量;模型列有 minimumWidth 兜底,
    // 加宽两列只是从模型列的富余里拿,不会挤压变形。
    // Enums 没有"列表列宽"令牌,这里是本组件的局部几何常量,只出现一次。
    readonly property int timeColumnWidth: 60
    readonly property int tokensColumnWidth: 92
    readonly property int costColumnWidth: 84

    height: Fluent.Enums.spacing.xxxl + Fluent.Enums.spacing.xs
    radius: Fluent.Enums.radius.large
    color: striped ? Fluent.Enums.alternateRowColor : Fluent.Enums.transparent

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Fluent.Enums.spacing.m
        anchors.rightMargin: Fluent.Enums.spacing.m
        spacing: Fluent.Enums.spacing.m

        Fluent.Label {
            Layout.preferredWidth: row.timeColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.timeText
            type: Fluent.Enums.label.type_caption
            font.pixelSize: Fluent.Enums.typography.micro
            customTextColor: Fluent.Enums.tertiaryForeground
            elide: Text.ElideRight
        }

        Fluent.Label {
            Layout.fillWidth: true
            Layout.minimumWidth: Fluent.Enums.spacing.xxxl * 2
            Layout.alignment: Qt.AlignVCenter
            text: row.modelText
            type: Fluent.Enums.label.type_caption
            font.pixelSize: Fluent.Enums.typography.captionCompact
            customTextColor: Fluent.Enums.secondaryForeground
            elide: Text.ElideRight
        }

        Fluent.Label {
            Layout.preferredWidth: row.tokensColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.tokensText
            type: Fluent.Enums.label.type_caption
            font.pixelSize: Fluent.Enums.typography.micro
            customTextColor: Fluent.Enums.tertiaryForeground
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }

        Fluent.Label {
            Layout.preferredWidth: row.costColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.costText
            type: Fluent.Enums.label.type_body_strong
            font.pixelSize: Fluent.Enums.typography.captionCompact
            customTextColor: Fluent.Enums.statusLevel.warningColor
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }
    }
}
