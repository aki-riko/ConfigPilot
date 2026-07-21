import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property string baseUrlValue: ""
    property string providerValue: ""
    property string wireApiValue: ""
    property bool hasKey: false
    property bool configBusy: false
    readonly property string keyDraft: keyInput.text

    signal baseUrlEdited(string value)
    signal providerEdited(string value)
    signal wireApiEdited(string value)
    signal saveKeyRequested(string value)

    function commitKey() {
        var value = keyInput.text.trim()
        if (value.length === 0) return
        root.saveKeyRequested(value)
        keyInput.text = ""
    }

    autoHeight: true

    Column {
        id: cardColumn
        objectName: "connectionCardColumn"
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
                    text: "连接与认证"
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.subtitle
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "配置 API 地址、协议和访问密钥"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Fluent.Badge {
                text: root.hasKey ? "密钥已设置" : "未设置密钥"
                level: root.hasKey
                       ? Fluent.Enums.statusLevel.success
                       : Fluent.Enums.statusLevel.warning
            }
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.xs

            Text {
                text: "API 地址"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                text: "base_url · 未包含 /v1 时自动补全"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
            }
            Fluent.LineEdit {
                id: baseUrlEdit
                objectName: "baseUrlEdit"
                width: parent.width
                placeholderText: "https://api.example.com/v1"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.baseUrlValue
                })
                onTextChanged: {
                    if (text !== root.baseUrlValue) root.baseUrlEdited(text)
                }
                Connections {
                    target: root
                    function onBaseUrlValueChanged() {
                        if (baseUrlEdit.text !== root.baseUrlValue) {
                            baseUrlEdit.text = root.baseUrlValue
                        }
                    }
                }
            }
        }

        GridLayout {
            id: connectionGrid
            objectName: "connectionGrid"
            width: cardColumn.innerWidth
            columns: width < 620 ? 1 : 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.l

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "提供商标识"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "provider"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.LineEdit {
                    id: providerEdit
                    objectName: "providerEdit"
                    Layout.fillWidth: true
                    placeholderText: "relay"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.providerValue
                    })
                    onTextChanged: {
                        if (text !== root.providerValue) root.providerEdited(text)
                    }
                    Connections {
                        target: root
                        function onProviderValueChanged() {
                            if (providerEdit.text !== root.providerValue) {
                                providerEdit.text = root.providerValue
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
                    text: "通信协议"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: "wire_api"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.LineEdit {
                    id: wireApiEdit
                    objectName: "wireApiEdit"
                    Layout.fillWidth: true
                    placeholderText: "responses"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.wireApiValue
                    })
                    onTextChanged: {
                        if (text !== root.wireApiValue) root.wireApiEdited(text)
                    }
                    Connections {
                        target: root
                        function onWireApiValueChanged() {
                            if (wireApiEdit.text !== root.wireApiValue) {
                                wireApiEdit.text = root.wireApiValue
                            }
                        }
                    }
                }
            }
        }

        Fluent.Separator {
            width: cardColumn.innerWidth
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.s

            Text {
                text: "API 密钥"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                width: parent.width
                text: "输入完成后自动保存；留空不会改动现有 auth.json"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }

            GridLayout {
                id: keyGrid
                width: parent.width
                columns: width < 560 ? 1 : 2
                columnSpacing: Fluent.Enums.spacing.m
                rowSpacing: Fluent.Enums.spacing.s

                Fluent.LineEdit {
                    id: keyInput
                    Layout.fillWidth: true
                    inputType: Fluent.Enums.input.type_password
                    enabled: !root.configBusy
                    placeholderText: "粘贴 API key"
                    onAccepted: root.commitKey()
                    onEditingFinished: root.commitKey()
                }
                Fluent.Button {
                    Layout.fillWidth: keyGrid.columns === 1
                    style: Fluent.Enums.button.style_default
                    text: "保存密钥"
                    enabled: !root.configBusy && keyInput.text.trim().length > 0
                    onClicked: root.commitKey()
                }
            }
        }
    }
}
