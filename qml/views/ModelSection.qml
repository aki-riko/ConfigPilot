import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property string modelValue: ""
    property string reasoningValue: ""
    property var availableModels: []

    signal modelTextEdited(string value)
    signal modelCommitted(string value)
    signal modelSelected(string value)
    signal effortSelected(string value)
    signal fetchRequested()

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
                    text: "模型与推理"
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.subtitle
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "选择模型时自动使用它支持的最高思考档位"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Fluent.Badge {
                text: root.availableModels.length > 0
                      ? root.availableModels.length + " 个模型"
                      : "未获取列表"
                level: root.availableModels.length > 0
                       ? Fluent.Enums.statusLevel.info
                       : Fluent.Enums.statusLevel.attention
            }
        }

        GridLayout {
            width: cardColumn.innerWidth
            columns: width < 680 ? 1 : 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.l

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "当前模型"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "model"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.LineEdit {
                    id: modelEdit
                    objectName: "modelEdit"
                    Layout.fillWidth: true
                    placeholderText: "例如 gpt-5.6-sol"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.modelValue
                    })
                    onTextChanged: {
                        if (text !== root.modelValue) root.modelTextEdited(text)
                    }
                    onEditingFinished: root.modelCommitted(text)
                    onAccepted: root.modelCommitted(text)
                    Connections {
                        target: root
                        function onModelValueChanged() {
                            if (modelEdit.text !== root.modelValue) {
                                modelEdit.text = root.modelValue
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
                    text: "在线模型列表"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "从当前 API 地址获取"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }

                GridLayout {
                    id: pickerGrid
                    Layout.fillWidth: true
                    columns: width < 330 ? 1 : 2
                    columnSpacing: Fluent.Enums.spacing.s
                    rowSpacing: Fluent.Enums.spacing.s

                    Fluent.ComboBoxDefault {
                        id: modelPicker
                        Layout.fillWidth: true
                        placeholderText: root.availableModels.length > 0
                                         ? "选择已获取模型"
                                         : "先获取模型"
                        model: root.availableModels
                        onActivated: function(index) {
                            if (index >= 0 && index < root.availableModels.length) {
                                root.modelSelected(root.availableModels[index])
                            }
                        }
                    }
                    Fluent.Button {
                        Layout.fillWidth: pickerGrid.columns === 1
                        style: Fluent.Enums.button.style_default
                        text: "获取模型"
                        onClicked: root.fetchRequested()
                    }
                }
            }
        }

        Fluent.Separator {
            width: cardColumn.innerWidth
        }

        ReasoningEffortSelector {
            width: cardColumn.innerWidth
            modelName: root.modelValue
            reasoningEffort: root.reasoningValue
            onEffortSelected: function(value) {
                root.effortSelected(value)
            }
        }
    }
}
