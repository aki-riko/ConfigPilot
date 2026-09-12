// "最近调用"单行:时间 / 模型 / Token(已简写) / 消耗金额,四列定宽对齐。
// 中间模型列占满剩余宽度,长模型名自动省略,不会把 Token 列挤变形。
// 配色走 PrismQML 主题令牌,深浅色自动跟随,与主程序同源。
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

    // 列宽:时间 / Token / 金额固定,模型列自适应(约 66px,足够常见的模型名)
    readonly property int timeColumnWidth: 60
    readonly property int tokensColumnWidth: 80
    readonly property int costColumnWidth: 54
    property int fontSize: 10

    height: 28
    radius: 8
    color: striped ? Fluent.Enums.alternateRowColor : "transparent"

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 8

        Text {
            Layout.preferredWidth: row.timeColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.timeText
            font.pixelSize: row.fontSize
            color: Fluent.Enums.tertiaryForeground
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 40
            Layout.alignment: Qt.AlignVCenter
            text: row.modelText
            font.pixelSize: row.fontSize + 1
            color: Fluent.Enums.secondaryForeground
            elide: Text.ElideRight
        }

        Text {
            Layout.preferredWidth: row.tokensColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.tokensText
            font.pixelSize: row.fontSize
            color: Fluent.Enums.tertiaryForeground
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }

        Text {
            Layout.preferredWidth: row.costColumnWidth
            Layout.alignment: Qt.AlignVCenter
            text: row.costText
            font.pixelSize: row.fontSize + 1
            font.bold: true
            color: Fluent.Enums.statusLevel.warningColor
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }
    }
}
