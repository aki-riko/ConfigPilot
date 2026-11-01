import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property string modelValue: ""
    property string reasoningValue: ""
    property var availableModels: []
    property bool loading: false

    signal modelTextEdited(string value)
    signal modelCommitted(string value)
    signal modelSelected(string value)
    signal effortSelected(string value)
    signal fetchRequested()

    title: "模型与推理"
    content: ""
    icon: Fluent.Enums.icon.brain
    expanded: false
    contentPadding: 0

    headerContent: Component {
        Fluent.Badge {
            text: root.availableModels.length > 0
                  ? root.availableModels.length + " 个模型"
                  : "未获取列表"
            level: root.availableModels.length > 0
                   ? Fluent.Enums.statusLevel.info
                   : Fluent.Enums.statusLevel.attention
        }
    }

    // 高度用 implicitHeight（含 padding）；childrenRect 不含 padding，
    // 会把卡片底部最后一行裁掉。
    Item {
        width: parent ? parent.width : 0
        implicitHeight: cardColumn.implicitHeight
        height: implicitHeight

        Column {
            id: cardColumn
            objectName: "modelCardColumn"
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            GridLayout {
                id: modelGrid
                objectName: "modelGrid"
                width: cardColumn.innerWidth
                columns: width < 680 ? 1 : 2
                uniformCellWidths: columns === 2
                columnSpacing: Fluent.Enums.spacing.l
                rowSpacing: Fluent.Enums.spacing.l
                readonly property real equalItemWidth: columns === 2
                                                       ? Math.max(
                                                             0,
                                                             (width - columnSpacing) / 2
                                                         )
                                                       : width

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: modelGrid.equalItemWidth
                    Layout.maximumWidth: modelGrid.equalItemWidth
                    label: "当前模型"
                    keyName: "model"

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

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: modelGrid.equalItemWidth
                    Layout.maximumWidth: modelGrid.equalItemWidth
                    label: "在线模型列表"
                    hint: "从当前 API 地址获取"

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Fluent.Enums.spacing.s

                        Fluent.ComboBoxDefault {
                            id: modelPicker
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
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
                            Layout.minimumWidth: 112
                            Layout.preferredWidth: 112
                            Layout.maximumWidth: 112
                            style: Fluent.Enums.button.style_default
                            icon: Fluent.Enums.icon.arrow_sync
                            text: root.loading ? "获取中..." : "获取模型"
                            enabled: !root.loading
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
}
