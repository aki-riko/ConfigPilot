import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

// 统一的表单字段容器：中文标签与英文键名同一行，下面是控件本身。
// 之前每个 Section 各写一套「大标题 + 英文键名」两行头，行高不一致、
// 网格错位，页面被拉得很长。改为一处定义、各页复用。
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

        ColumnLayout {
            id: fieldHost
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.xs
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.hint
            visible: text.length > 0
            color: Fluent.Enums.textColor.tertiary
            font.pixelSize: Fluent.Enums.typography.caption
            font.family: Fluent.Enums.fontFamily
            wrapMode: Text.WordWrap
        }
    }
}
