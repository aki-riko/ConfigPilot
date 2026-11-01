import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

// 统一的表单字段容器：中文标签与英文键名同一行，下面依次是说明文字、控件本体。
// 之前每个 Section 各写一套「大标题 + 英文键名」两行头，行高不一致、
// 网格错位，页面被拉得很长。改为一处定义、各页复用。
//
// 行序固定为「标题 → 说明 → 控件」：说明行即使为空也保留一行高度
// （用空格撑出行高）。否则同一 GridLayout 里带 hint 的字段比兄弟字段高，
// 兄弟字段会被垂直居中压偏半行，控件顶部对不齐。
//
// 根节点用 Item、内部用 ColumnLayout：本组件既会被放进普通 Column
// （ConnectionSection 等），也会被放进 GridLayout（Claude 各节）。
// 普通 Column 不给 Layout 子项赋 width，根节点直接写 ColumnLayout 会
// 得到 0 宽，内部 Layout.fillWidth 的控件跟着塌成 0 高；这里显式把
// fieldColumn 的宽度绑到自身宽度即可两处通用。
Item {
    id: root

    property string label: ""
    property string keyName: ""
    property string hint: ""
    // 控件本体放这里，子项用 Layout.* 描述尺寸。
    default property alias fieldContent: fieldHost.data

    // 标题顶部对齐：说明文字换行时字段会变高，不能靠垂直居中去凑。
    Layout.alignment: Qt.AlignTop

    implicitHeight: fieldColumn.implicitHeight
    height: implicitHeight

    ColumnLayout {
        id: fieldColumn
        width: root.width
        spacing: Fluent.Enums.spacing.xs

        RowLayout {
            id: labelRow
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.xs

            Text {
                id: labelText
                // 常量上限而不是引用自身宽度：Layout 里引用父项宽度会触发
                // Qt Quick Layouts 的递归重排（Detected recursive rearrange）。
                Layout.maximumWidth: 280
                text: root.label
                visible: text.length > 0
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Text {
                id: keyText
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.keyName
                visible: text.length > 0
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }
        }

        Text {
            id: hintText
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            // 没有 hint 时用一个空格占位：既保留说明行高度让同排字段对齐，
            // 又不会渲染出可见文字。
            text: root.hint.length > 0 ? root.hint : " "
            color: Fluent.Enums.textColor.tertiary
            font.pixelSize: Fluent.Enums.typography.caption
            font.family: Fluent.Enums.fontFamily
            wrapMode: Text.WordWrap
        }

        ColumnLayout {
            id: fieldHost
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.xs
        }
    }
}
