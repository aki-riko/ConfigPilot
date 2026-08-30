import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property string endpointValue: ""
    property string authSchemeValue: "bearer"
    property string apiKeyValue: ""
    property bool hasApiKey: false
    property bool clearApiKeyValue: false
    readonly property int controlHeight: Fluent.Enums.controlSize.inputHeight

    signal endpointEdited(string value)
    signal authSchemeSelected(string value)
    signal apiKeyEdited(string value)
    signal clearApiKeyToggled(bool value)

    autoHeight: true

    Column {
        id: cardColumn
        width: parent ? parent.width : 0
        leftPadding: Fluent.Enums.spacing.l
        rightPadding: Fluent.Enums.spacing.l
        topPadding: Fluent.Enums.spacing.m
        bottomPadding: Fluent.Enums.spacing.m
        spacing: Fluent.Enums.spacing.s

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
                    text: "网关连接"
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.subtitle
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "兼容 Anthropic /v1/messages 的第三方推理入口"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: root.hasApiKey ? "已保存密钥" : "尚未保存密钥"
                color: root.hasApiKey
                       ? Fluent.Enums.statusLevel.successColor
                       : Fluent.Enums.statusLevel.warningColor
                font.pixelSize: Fluent.Enums.typography.caption
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.xxs

            Text {
                text: "网关地址"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.caption
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Fluent.LineEdit {
                id: endpointEdit
                objectName: "claudeEndpointEdit"
                width: parent.width
                height: root.controlHeight
                placeholderText: "https://llm-gateway.example.com（原样写入）"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.endpointValue
                })
                onTextChanged: {
                    if (text !== root.endpointValue) root.endpointEdited(text)
                }
                Connections {
                    target: root
                    function onEndpointValueChanged() {
                        if (endpointEdit.text !== root.endpointValue) {
                            endpointEdit.text = root.endpointValue
                        }
                    }
                }
            }
        }

        GridLayout {
            id: gatewayGrid
            width: cardColumn.innerWidth
            columns: width < 620 ? 1 : 2
            uniformCellWidths: columns === 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.s
            readonly property real equalItemWidth: columns === 2
                                                   ? Math.max(
                                                         0,
                                                         (width - columnSpacing) / 2
                                                     )
                                                   : width

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: gatewayGrid.equalItemWidth
                Layout.maximumWidth: gatewayGrid.equalItemWidth
                Layout.alignment: Qt.AlignTop
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "认证方式"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.ComboBoxDefault {
                    id: authSchemeBox
                    objectName: "claudeAuthSchemeBox"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.controlHeight
                    property var options: [
                        { "text": "Authorization: Bearer", "value": "bearer" },
                        { "text": "x-api-key", "value": "x-api-key" }
                    ]
                    model: options

                    function syncCurrentIndex() {
                        var found = 0
                        for (var i = 0; i < options.length; i++) {
                            if (options[i].value === root.authSchemeValue) found = i
                        }
                        if (currentIndex !== found) currentIndex = found
                    }

                    Component.onCompleted: Qt.callLater(syncCurrentIndex)
                    onActivated: function(index) {
                        if (index >= 0 && index < options.length) {
                            root.authSchemeSelected(options[index].value)
                        }
                    }
                    Connections {
                        target: root
                        function onAuthSchemeValueChanged() {
                            authSchemeBox.syncCurrentIndex()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Fluent.Enums.controlSize.checkboxOuter

                    Text {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        text: root.authSchemeValue === "x-api-key"
                              ? "密钥将写入 x-api-key 请求头"
                              : "密钥将作为 Bearer Token 发送"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: gatewayGrid.equalItemWidth
                Layout.maximumWidth: gatewayGrid.equalItemWidth
                Layout.alignment: Qt.AlignTop
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "API 密钥"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.LineEdit {
                    id: apiKeyEdit
                    objectName: "claudeApiKeyEdit"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.controlHeight
                    inputType: Fluent.Enums.input.type_password
                    enabled: !root.clearApiKeyValue
                    placeholderText: root.hasApiKey
                                     ? "已保存；留空保持不变"
                                     : "粘贴第三方 API key"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.apiKeyValue
                    })
                    onTextChanged: {
                        if (text !== root.apiKeyValue) root.apiKeyEdited(text)
                    }
                    Connections {
                        target: root
                        function onApiKeyValueChanged() {
                            if (apiKeyEdit.text !== root.apiKeyValue) {
                                apiKeyEdit.text = root.apiKeyValue
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Fluent.Enums.controlSize.checkboxOuter
                    spacing: Fluent.Enums.spacing.s

                    Text {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        text: root.hasApiKey
                              ? "留空将保留当前密钥"
                              : "仅写入本机 Claude 配置"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }

                    Fluent.Toggle {
                        id: clearKeyToggle
                        objectName: "claudeClearKeyToggle"
                        Layout.alignment: Qt.AlignVCenter
                        enabled: root.hasApiKey
                        visible: root.hasApiKey
                        controlType: Fluent.Enums.toggle.control_checkbox
                        type: Fluent.Enums.toggle.type_default
                        text: "应用时删除"
                        Component.onCompleted: Qt.callLater(function() {
                            checked = root.clearApiKeyValue
                        })
                        onToggled: function(checkedValue) {
                            root.clearApiKeyToggled(checkedValue)
                        }
                        Connections {
                            target: root
                            function onClearApiKeyValueChanged() {
                                if (clearKeyToggle.checked !== root.clearApiKeyValue) {
                                    clearKeyToggle.checked = root.clearApiKeyValue
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
