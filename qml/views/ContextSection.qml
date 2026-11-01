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

    headerContent: Component {
        Fluent.Badge {
            text: root.currentPreset.menuText || "自定义"
            level: root.currentPreset.contextWindow
                   ? Fluent.Enums.statusLevel.info
                   : Fluent.Enums.statusLevel.attention
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

            Flow {
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.m

                Fluent.Button {
                    width: 152
                    Layout.minimumWidth: 152
                    Layout.preferredWidth: 152
                    Layout.maximumWidth: 152
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.checkmark
                    text: "套用稳定上下文"
                    enabled: root.currentPreset.contextWindow > 0
                    onClicked: root.presetRequested()
                }
                Fluent.Button {
                    width: 152
                    Layout.minimumWidth: 152
                    Layout.preferredWidth: 152
                    Layout.maximumWidth: 152
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.checkmark
                    text: "套用百万上下文"
                    enabled: root.millionPreset.contextWindow > 0
                    onClicked: root.millionPresetRequested()
                }
                Fluent.Button {
                    width: 128
                    Layout.minimumWidth: 128
                    Layout.preferredWidth: 128
                    Layout.maximumWidth: 128
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.icon_delete
                    text: "清空自定义值"
                    onClicked: root.clearRequested()
                }
            }

            Column {
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.s

                RowLayout {
                    width: parent.width
                    spacing: Fluent.Enums.spacing.s

                    Text {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: "自动压缩阈值占上下文窗口"
                        color: Fluent.Enums.textColor.secondary
                        font.pixelSize: Fluent.Enums.typography.body
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }
                    Text {
                        id: compactRatioValue
                        text: root.compactRatioText
                        color: Fluent.Enums.textColor.primary
                        font.pixelSize: Fluent.Enums.typography.body
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }
                }
                Fluent.ProgressBar {
                    width: parent.width
                    from: 0
                    to: 1
                    value: root.compactRatio
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
