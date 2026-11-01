import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

// 统一的表单字段容器。
//
// 行序约定：左侧是「标题 → 说明」的标签列，右侧是控件本体，即「标签内联」。
// 之前是「标题 → 说明 → 控件」三行纵向堆叠，一个字段固定吃掉 50~66px，
// 一屏放不下几个字段；改成左右分栏后，单字段高度收敛到控件自身高度
// （约 32~40px），带说明的字段也不再额外多占一行。
//
// 各节统一按单列使用（一个字段一行、占满整行宽度），字段内部才是左右两栏。
// 不要把这些字段并排塞进多列 GridLayout：并排时带说明的字段比兄弟高，
// GridLayout 会把矮的那个垂直居中，两列控件顶部就错开了。
//
// 根节点用 Item、内部用 RowLayout：本组件既会被放进普通 Column
// （ConnectionSection 等），也会被放进 Layout（Claude 各节）。
// 普通 Column 不给 Layout 子项赋 width，根节点直接写 RowLayout 会
// 得到 0 宽，内部 Layout.fillWidth 的控件跟着塌成 0 高；这里显式把
// fieldRow 的宽度绑到自身宽度即可两处通用。
Item {
    id: root

    property string label: ""
    property string keyName: ""
    property string hint: ""
    // 控件本体放这里，子项用 Layout.* 描述尺寸。
    default property alias fieldContent: fieldHost.data
    // 标签列宽度。0 表示按可用宽度自适应；控件特别窄的场合可以显式写死。
    property int labelWidth: 0
    // 自适应宽度：宽窗口给到 280 让长说明一句放得下，窄窗口收缩但保底 160，
    // 避免标签列把控件挤到不可用。只依赖 root.width（不用标签列自身几何），
    // 不会触发 Qt Quick Layouts 的递归重排。
    readonly property int effectiveLabelWidth: root.labelWidth > 0
                                             ? root.labelWidth
                                             : Math.max(160, Math.min(
                                                   280, Math.round(root.width * 0.3)))

    // 字段整体在父布局里顶部对齐：说明文字换行时字段会变高，不能靠垂直居中凑。
    Layout.alignment: Qt.AlignTop

    implicitHeight: fieldRow.implicitHeight
    height: implicitHeight

    RowLayout {
        id: fieldRow
        width: root.width
        spacing: Fluent.Enums.spacing.l

        // 左侧标签列：标题与英文键名同行，说明文字在其下，控件保持右侧对齐。
        ColumnLayout {
            id: fieldLabelColumn
            objectName: "fieldLabelColumn"
            Layout.alignment: Qt.AlignTop
            Layout.minimumWidth: 0
            Layout.preferredWidth: root.effectiveLabelWidth
            Layout.maximumWidth: root.effectiveLabelWidth
            spacing: Fluent.Enums.spacing.xxs

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

            // 没有说明文字时整行让位，标签列只留标题行的高度。
            Text {
                id: hintText
                objectName: "fieldHintText"
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

        ColumnLayout {
            id: fieldHost
            objectName: "fieldHost"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignTop
            spacing: Fluent.Enums.spacing.xs
        }
    }
}
