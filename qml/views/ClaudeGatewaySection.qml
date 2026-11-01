import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
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

    title: "网关连接"
    content: ""
    icon: Fluent.Enums.icon.server
    expanded: true
    contentPadding: 0

    headerContent: Component {
        Fluent.Badge {
            text: root.hasApiKey ? "已保存密钥" : "尚未保存密钥"
            level: root.hasApiKey
                   ? Fluent.Enums.statusLevel.success
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
            objectName: "claudeGatewayCardColumn"
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            FormField {
                width: cardColumn.innerWidth
                label: "网关地址"
                keyName: "endpoint"
                hint: "原样写入，不自动补全路径"

                Fluent.LineEdit {
                    id: endpointEdit
                    objectName: "claudeEndpointEdit"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.controlHeight
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

            // 字段一律单列纵向堆叠、占满整行：并排两列时带说明的字段比兄弟
            // 高一截，GridLayout 会把矮的垂直居中，控件顶部就错开了。
            ColumnLayout {
                id: gatewayGrid
                objectName: "gatewayGrid"
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.l

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    label: "认证方式"
                    keyName: "auth"
                    hint: root.authSchemeValue === "x-api-key"
                          ? "密钥将写入 x-api-key 请求头"
                          : "密钥将作为 Bearer Token 发送"

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
                }

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    label: "API 密钥"
                    hint: root.hasApiKey
                          ? "修改后随「应用更改」写入"
                          : "仅写入本机 Claude 配置；填写后随「应用更改」写入"

                    // 遮罩与眼睛切换全部交给 PrismQML 的 LineEdit：
                    // type_password 会内置眼睛按钮并自动切换 showPassword，
                    // 不需要在外部再叠一个显隐按钮（那样会出现两个眼睛）。
                    Fluent.LineEdit {
                        id: apiKeyEdit
                        objectName: "claudeApiKeyEdit"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: root.controlHeight
                        inputType: Fluent.Enums.input.type_password
                        enabled: !root.clearApiKeyValue
                        placeholderText: "粘贴第三方 API key"
                        Component.onCompleted: Qt.callLater(function() {
                            text = root.apiKeyValue
                        })
                        onTextChanged: {
                            if (text !== root.apiKeyValue) root.apiKeyEdited(text)
                        }
                        Connections {
                            target: root
                            function onApiKeyValueChanged() {
                                // 只在用户没在编辑时回填，避免把正在输入的草稿冲掉。
                                if (!apiKeyEdit.activeFocus
                                        && apiKeyEdit.text !== root.apiKeyValue) {
                                    apiKeyEdit.text = root.apiKeyValue
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: Fluent.Enums.controlSize.checkboxOuter
                        spacing: Fluent.Enums.spacing.s

                        Item {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            implicitHeight: 1
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
}
