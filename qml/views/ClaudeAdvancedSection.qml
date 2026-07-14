import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property string modelsValue: ""
    property string headersValue: ""
    property int headerCount: 0
    property bool clearHeadersValue: false

    signal modelsEdited(string value)
    signal headersEdited(string value)
    signal clearHeadersToggled(bool value)

    title: "模型与额外 Header"
    content: "高级配置 · 可选覆盖模型发现和额外请求头"
    expanded: false

    GridLayout {
        id: advancedGrid
        width: parent ? parent.width : 0
        columns: width < 680 ? 1 : 2
        columnSpacing: Fluent.Enums.spacing.l
        rowSpacing: Fluent.Enums.spacing.l

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.xs

            Text {
                Layout.fillWidth: true
                text: "Model list"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                Layout.fillWidth: true
                text: "每行一个，第一个为默认；留空使用 /v1/models"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
            Fluent.TextEdit {
                id: modelsEdit
                objectName: "claudeModelsEdit"
                Layout.fillWidth: true
                Layout.preferredHeight: 108
                placeholderText: "claude-sonnet-4-6\nclaude-opus-4-6"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.modelsValue
                })
                onTextEdited: {
                    if (text !== root.modelsValue) root.modelsEdited(text)
                }
                Connections {
                    target: root
                    function onModelsValueChanged() {
                        if (modelsEdit.text !== root.modelsValue) {
                            modelsEdit.text = root.modelsValue
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
                Layout.fillWidth: true
                text: root.headerCount > 0
                      ? "额外 Header · 已保存 " + root.headerCount + " 项"
                      : "额外 Header · 可选"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                Layout.fillWidth: true
                text: "输入 JSON 对象覆盖现有值；敏感内容不会回显"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
            Fluent.TextEdit {
                id: headersEdit
                objectName: "claudeHeadersEdit"
                Layout.fillWidth: true
                Layout.preferredHeight: 108
                enabled: !root.clearHeadersValue
                placeholderText: "{\n  \"X-Tenant\": \"tenant-id\"\n}"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.headersValue
                })
                onTextEdited: {
                    if (text !== root.headersValue) root.headersEdited(text)
                }
                Connections {
                    target: root
                    function onHeadersValueChanged() {
                        if (headersEdit.text !== root.headersValue) {
                            headersEdit.text = root.headersValue
                        }
                    }
                }
            }
            Fluent.Toggle {
                id: clearHeadersToggle
                enabled: root.headerCount > 0
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_default
                text: "移除已保存 Header"
                Component.onCompleted: Qt.callLater(function() {
                    checked = root.clearHeadersValue
                })
                onToggled: function(checkedValue) {
                    root.clearHeadersToggled(checkedValue)
                }
                Connections {
                    target: root
                    function onClearHeadersValueChanged() {
                        if (clearHeadersToggle.checked !== root.clearHeadersValue) {
                            clearHeadersToggle.checked = root.clearHeadersValue
                        }
                    }
                }
            }
        }
    }
}
