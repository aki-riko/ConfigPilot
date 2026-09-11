// 余额监控桌宠的设置窗口:无边框置顶小窗,保存经 NewApiPet.saveSettings 校验。
import QtQuick
import QtQuick.Window

Window {
    id: dialog

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    width: 392
    height: 452
    visible: false
    title: "余额监控设置"

    readonly property bool petReady: typeof NewApiPet !== "undefined" && NewApiPet !== null
    readonly property bool managerReady: typeof PetManager !== "undefined" && PetManager !== null
    property string currency: "CNY"

    // 由 PetManager.openSettings() 唤起:主界面设置页按钮与桌宠右键菜单都走这里。
    Connections {
        target: managerReady ? PetManager : null
        function onOpenSettingsRequested() { dialog.openForEdit() }
    }

    function openForEdit() {
        if (petReady) {
            baseField.text = NewApiPet.configBaseUrl
            keyField.text = NewApiPet.configApiKey
            intervalField.text = NewApiPet.configIntervalText
            dialog.currency = NewApiPet.configCurrency
            perUnitField.text = NewApiPet.configQuotaPerUnitText
            rateField.text = NewApiPet.configCnyRateText
            imageField.text = NewApiPet.configPetImage
        }
        errorText.text = ""
        x = Math.max(0, Screen.desktopAvailableWidth / 2 - width / 2)
        y = Math.max(0, Screen.desktopAvailableHeight / 2 - height / 2)
        visible = true
        baseField.focusInput()
    }

    function save() {
        if (!petReady) return
        var ok = NewApiPet.saveSettings(
            baseField.text, keyField.text, intervalField.text, dialog.currency,
            perUnitField.text, rateField.text, imageField.text)
        if (ok) {
            visible = false
            return
        }
        errorText.text = NewApiPet.saveErrorText
    }

    Rectangle {
        id: card
        anchors.fill: parent
        radius: 16
        color: "#F7F9FF"
        border.color: "#D9E1F5"

        Column {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10

            Item {
                width: parent.width
                height: 26

                Text {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "余额监控设置"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#2B3252"
                }
                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: closeBtnArea.containsMouse ? "#E4E7EF" : "#EDF0F7"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 16; color: "#5B6478" }
                    MouseArea {
                        id: closeBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: dialog.visible = false
                    }
                }
            }

            LabeledField {
                id: baseField
                width: parent.width
                label: "接口地址(new-api 站点根地址)"
                placeholder: "https://api.example.com"
            }

            LabeledField {
                id: keyField
                width: parent.width
                label: "API Key(仅本地保存,也可用环境变量 CONFIGPILOT_NEWAPI_KEY)"
                placeholder: "sk-..."
            }

            Row {
                width: parent.width
                spacing: 10

                LabeledField {
                    id: intervalField
                    width: (parent.width - 10) / 2
                    label: "轮询间隔(秒,5-3600)"
                    placeholder: "60"
                    validator: RegularExpressionValidator { regularExpression: /[0-9]+/ }
                }

                Column {
                    width: (parent.width - 10) / 2
                    spacing: 4

                    Text {
                        text: "额度展示类型"
                        font.pixelSize: 11
                        color: "#8A93A6"
                    }
                    Row {
                        spacing: 6

                        Repeater {
                            model: ["CNY", "USD", "TOKENS"]

                            delegate: Rectangle {
                                width: 64
                                height: 28
                                radius: 14
                                color: dialog.currency === modelData ? "#3E5BD8" : "#FFFFFF"
                                border.color: dialog.currency === modelData ? "#3E5BD8" : "#C9D3EC"

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData
                                    font.pixelSize: 11
                                    color: dialog.currency === modelData ? "#FFFFFF" : "#5B6478"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: dialog.currency = modelData
                                }
                            }
                        }
                    }
                }
            }

            Row {
                width: parent.width
                spacing: 10

                LabeledField {
                    id: perUnitField
                    width: (parent.width - 10) / 2
                    label: "$ 对应额度(默认 500000)"
                    placeholder: "500000"
                    validator: RegularExpressionValidator { regularExpression: /[0-9]+(\.[0-9]+)?/ }
                }

                LabeledField {
                    id: rateField
                    width: (parent.width - 10) / 2
                    label: "USD→CNY 汇率(默认 7.3)"
                    placeholder: "7.3"
                    validator: RegularExpressionValidator { regularExpression: /[0-9]+(\.[0-9]+)?/ }
                }
            }

            LabeledField {
                id: imageField
                width: parent.width
                label: "桌宠图片路径(可选,留空使用内置小飞宠)"
                placeholder: "D:\\pictures\\pet.png"
            }

            Text {
                id: errorText
                width: parent.width
                text: ""
                font.pixelSize: 11
                color: "#D5484A"
                wrapMode: Text.WrapAnywhere
                visible: text !== ""
            }

            Item { width: 1; height: 1 }

            Row {
                anchors.right: parent.right
                spacing: 10

                Rectangle {
                    width: 88
                    height: 32
                    radius: 16
                    color: cancelArea.containsMouse || cancelArea.pressed ? "#E8ECF5" : "#EEF1F8"

                    Text {
                        anchors.centerIn: parent
                        text: "取消"
                        font.pixelSize: 13
                        color: "#5B6478"
                    }
                    MouseArea {
                        id: cancelArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: dialog.visible = false
                    }
                }

                Rectangle {
                    width: 88
                    height: 32
                    radius: 16
                    color: saveArea.pressed ? "#3249B8" : (saveArea.containsMouse ? "#4465E4" : "#3E5BD8")

                    Text {
                        anchors.centerIn: parent
                        text: "保存并刷新"
                        font.pixelSize: 13
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: saveArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: dialog.save()
                    }
                }
            }

            Text {
                width: parent.width
                text: "站点若无 CNY 展示,汇率与 $ 额度需与 new-api 系统设置中的 QuotaPerUnit 保持一致。"
                font.pixelSize: 10
                color: "#A6ADC0"
                wrapMode: Text.WrapAnywhere
            }
        }
    }

    // ---------------------------------------------------------------- 输入框组件
    component LabeledField: Column {
        id: fieldRoot

        property alias label: labelText.text
        property alias text: input.text
        property alias placeholder: hint.text
        property alias validator: input.validator
        property bool invalid: false

        function focusInput() { input.forceActiveFocus() }

        spacing: 4

        Text {
            id: labelText
            font.pixelSize: 11
            color: "#8A93A6"
        }

        Rectangle {
            id: fieldBg
            width: parent.width
            height: 32
            radius: 8
            color: "#FFFFFF"
            border.color: input.activeFocus ? "#3E5BD8" : (fieldRoot.invalid ? "#D5484A" : "#C9D3EC")
            border.width: input.activeFocus ? 2 : 1

            TextInput {
                id: input
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                font.pixelSize: 12
                color: "#2B3252"
                clip: true
                selectByMouse: true
                verticalAlignment: TextInput.AlignVCenter

                Keys.onReturnPressed: dialog.save()
                Keys.onEnterPressed: dialog.save()

                Text {
                    id: hint
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    font.pixelSize: 12
                    color: "#B4BAC9"
                    visible: input.text === "" && !input.activeFocus
                }
            }
        }
    }
}
