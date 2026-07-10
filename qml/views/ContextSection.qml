import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property var currentPreset: ({})
    property var presetOptions: []
    property string contextWindowValue: ""
    property string autoCompactValue: ""
    property string toolOutputValue: ""
    property real compactRatio: 0
    property string compactRatioText: "未设置"

    signal presetRequested(string profileId)
    signal contextWindowEdited(string value)
    signal autoCompactEdited(string value)
    signal toolOutputEdited(string value)
    signal clearRequested()

    autoHeight: true

    Column {
        id: cardColumn
        width: parent ? parent.width : 0
        leftPadding: Fluent.Enums.spacing.xl
        rightPadding: Fluent.Enums.spacing.xl
        topPadding: Fluent.Enums.spacing.xl
        bottomPadding: Fluent.Enums.spacing.xl
        spacing: Fluent.Enums.spacing.l

        readonly property real innerWidth: Math.max(
            0, width - leftPadding - rightPadding
        )

        RowLayout {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "上下文预算"
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.subtitle
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "控制窗口大小、自动压缩阈值和工具输出保留量"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Fluent.Badge {
                text: root.currentPreset.menuText || "自定义"
                level: root.currentPreset.contextWindow
                       ? Fluent.Enums.statusLevel.info
                       : Fluent.Enums.statusLevel.attention
            }
        }

        Flow {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.m

            Fluent.Button {
                style: Fluent.Enums.button.style_default
                feature: Fluent.Enums.button.feature_dropdown
                text: "套用上下文预设"
                menuItems: root.presetOptions
                enabled: root.presetOptions.length > 0
                onMenuItemClicked: function(index, text) {
                    if (index >= 0 && index < root.presetOptions.length) {
                        root.presetRequested(root.presetOptions[index].id)
                    }
                }
            }
            Fluent.Button {
                style: Fluent.Enums.button.style_default
                text: "清空自定义值"
                onClicked: root.clearRequested()
            }
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.s

            RowLayout {
                width: parent.width
                Text {
                    Layout.fillWidth: true
                    text: "自动压缩阈值占上下文窗口"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
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

        GridLayout {
            width: cardColumn.innerWidth
            columns: width < 440 ? 1 : (width < 720 ? 2 : 3)
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.l

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "上下文窗口"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "model_context_window"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
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

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "自动压缩阈值"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "model_auto_compact_token_limit"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
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

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "工具输出保留"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "tool_output_token_limit"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
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
