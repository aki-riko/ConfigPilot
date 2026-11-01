import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property var currentPreset: ({})
    property var millionPreset: ({})
    property string contextWindowValue: ""
    property string autoCompactValue: ""
    property string toolOutputValue: ""
    property real compactRatio: 0
    property string compactRatioText: "未设置"

    signal presetRequested()
    signal millionPresetRequested()
    signal contextWindowEdited(string value)
    signal autoCompactEdited(string value)
    signal toolOutputEdited(string value)
    signal clearRequested()

    title: "上下文预算"
    content: ""
    icon: Fluent.Enums.icon.data_usage
    expanded: false
    contentPadding: 0

    // 预设动作收进头部的一个下拉按钮：三个按钮横铺会一直占着内容区一整行，
    // 而这三个操作都是低频的「一次性套用」，放到标题栏不额外占内容高度。
    // 菜单项只列当前可用的预设（不存在的预设直接不出现），
    // 因为 PrismQML 内置下拉菜单不读 itemEnabled，做不了单项置灰。
    readonly property var presetActions: {
        var items = []
        if (root.currentPreset.contextWindow > 0) {
            items.push({ "text": "套用稳定上下文", "icon": Fluent.Enums.icon.checkmark })
        }
        if (root.millionPreset.contextWindow > 0) {
            items.push({ "text": "套用百万上下文", "icon": Fluent.Enums.icon.checkmark })
        }
        if (items.length > 0) items.push("-")
        items.push({ "text": "清空自定义值", "icon": Fluent.Enums.icon.icon_delete })
        return items
    }

    readonly property int presetButtonWidth: 132

    headerContent: Component {
        RowLayout {
            spacing: Fluent.Enums.spacing.s

            Fluent.Badge {
                text: root.currentPreset.menuText || "自定义"
                level: root.currentPreset.contextWindow
                       ? Fluent.Enums.statusLevel.info
                       : Fluent.Enums.statusLevel.attention
            }

            Fluent.Button {
                objectName: "contextPresetDropdown"
                Layout.minimumWidth: root.presetButtonWidth
                Layout.preferredWidth: root.presetButtonWidth
                Layout.maximumWidth: root.presetButtonWidth
                style: Fluent.Enums.button.style_default
                feature: Fluent.Enums.button.feature_dropdown
                icon: Fluent.Enums.icon.options
                text: "上下文预设"
                menuItems: root.presetActions
                enabled: root.presetActions.length > 0
                onMenuItemClicked: function(index, text) {
                    // 菜单项都是动态拼的，按文本分发，避免菜单增删后索引错位。
                    if (text === "套用稳定上下文") root.presetRequested()
                    else if (text === "套用百万上下文") root.millionPresetRequested()
                    else if (text === "清空自定义值") root.clearRequested()
                }
            }
        }
    }

    // 高度用 implicitHeight（含 padding）；childrenRect 不含 padding 会裁掉底部。
    Item {
        width: parent ? parent.width : 0
        implicitHeight: cardColumn.implicitHeight
        height: implicitHeight

        Column {
            id: cardColumn
            objectName: "contextCardColumn"
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            // 占比这块也是「标签在左、控件在右」：以前标题一行、进度条一行，
            // 白白占掉两行高度；进度条本身只有几个像素高，跟标题同一行更紧凑。
            RowLayout {
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.l

                Text {
                    Layout.preferredWidth: 280
                    Layout.maximumWidth: 280
                    text: "自动压缩阈值占上下文窗口"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                    elide: Text.ElideRight
                }

                Fluent.ProgressBar {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignVCenter
                    from: 0
                    to: 1
                    value: root.compactRatio
                }

                Text {
                    id: compactRatioValue
                    Layout.alignment: Qt.AlignVCenter
                    text: root.compactRatioText
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
            }

            // 字段一律单列纵向堆叠、占满整行：并排多列时带说明的字段比兄弟
            // 高一截，GridLayout 会把矮的垂直居中，控件顶部就错开了。
            ColumnLayout {
                id: contextGrid
                objectName: "contextGrid"
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.l

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    label: "上下文窗口"
                    keyName: "model_context_window"

                    Fluent.LineEdit {
                        id: contextWindowEdit
                        objectName: "contextWindowEdit"
                        Layout.fillWidth: true
                        placeholderText: root.currentPreset.contextWindow
                                         ? String(root.currentPreset.contextWindow)
                                         : "未设置"
                        validator: IntValidator { bottom: 1 }
                        inputMethodHints: Qt.ImhDigitsOnly
                        Component.onCompleted: Qt.callLater(function() {
                            text = root.contextWindowValue
                        })
                        onTextChanged: {
                            if (text !== root.contextWindowValue) {
                                root.contextWindowEdited(text)
                            }
                        }
                        Connections {
                            target: root
                            function onContextWindowValueChanged() {
                                if (contextWindowEdit.text !== root.contextWindowValue) {
                                    contextWindowEdit.text = root.contextWindowValue
                                }
                            }
                        }
                    }
                }

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    label: "自动压缩阈值"
                    keyName: "model_auto_compact_token_limit"

                    Fluent.LineEdit {
                        id: autoCompactEdit
                        objectName: "autoCompactEdit"
                        Layout.fillWidth: true
                        placeholderText: root.currentPreset.autoCompactLimit
                                         ? String(root.currentPreset.autoCompactLimit)
                                         : "未设置"
                        validator: IntValidator { bottom: 1 }
                        inputMethodHints: Qt.ImhDigitsOnly
                        Component.onCompleted: Qt.callLater(function() {
                            text = root.autoCompactValue
                        })
                        onTextChanged: {
                            if (text !== root.autoCompactValue) {
                                root.autoCompactEdited(text)
                            }
                        }
                        Connections {
                            target: root
                            function onAutoCompactValueChanged() {
                                if (autoCompactEdit.text !== root.autoCompactValue) {
                                    autoCompactEdit.text = root.autoCompactValue
                                }
                            }
                        }
                    }
                }

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    label: "工具输出保留"
                    keyName: "tool_output_token_limit"

                    Fluent.LineEdit {
                        id: toolOutputEdit
                        objectName: "toolOutputEdit"
                        Layout.fillWidth: true
                        placeholderText: root.currentPreset.toolOutputLimit
                                         ? String(root.currentPreset.toolOutputLimit)
                                         : "6000"
                        validator: IntValidator { bottom: 1 }
                        inputMethodHints: Qt.ImhDigitsOnly
                        Component.onCompleted: Qt.callLater(function() {
                            text = root.toolOutputValue
                        })
                        onTextChanged: {
                            if (text !== root.toolOutputValue) {
                                root.toolOutputEdited(text)
                            }
                        }
                        Connections {
                            target: root
                            function onToolOutputValueChanged() {
                                if (toolOutputEdit.text !== root.toolOutputValue) {
                                    toolOutputEdit.text = root.toolOutputValue
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
