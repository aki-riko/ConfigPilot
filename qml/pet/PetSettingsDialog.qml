// 余额监控桌宠的设置窗口:优先复用 Codex/Claude 已配好的接口与 Key。
import QtQuick
import QtQuick.Window

Window {
    id: dialog

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    width: 400
    height: 704
    visible: false
    title: "余额监控设置"

    readonly property bool petReady: typeof NewApiPet !== "undefined" && NewApiPet !== null
    readonly property bool managerReady: typeof PetManager !== "undefined" && PetManager !== null
    property string currency: "CNY"
    property string source: "auto"
    property string balanceSource: "auto"
    property var sources: []

    // 余额口径:自动 / 令牌额度 / 账户余额(账户余额要求站点关闭 DisplayTokenStatEnabled)
    readonly property var balanceOptions: [
        { "id": "auto", "label": "自动" },
        { "id": "token", "label": "令牌额度" },
        { "id": "account", "label": "账户余额" }
    ]

    readonly property bool manualMode: source === "manual"
    // 当前所选来源解析出的站点根(用于展示"复用 XX")。
    readonly property string selectedSite: {
        if (source === "manual") return baseField.text
        for (var i = 0; i < sources.length; ++i) {
            if (sources[i].id === source) return sources[i].site
        }
        return ""
    }
    readonly property string selectedLabel: {
        for (var i = 0; i < sources.length; ++i) {
            if (sources[i].id === source) return sources[i].label
        }
        return source === "auto" ? "自动复用" : "手动填写"
    }

    // 由 PetManager.openSettings() 唤起:主界面设置页按钮与桌宠右键菜单都走这里。
    Connections {
        target: managerReady ? PetManager : null
        function onOpenSettingsRequested() { dialog.openForEdit() }
    }

    function openForEdit() {
        if (petReady) {
            dialog.source = NewApiPet.currentSource
            dialog.sources = NewApiPet.petSources
            baseField.text = NewApiPet.configBaseUrl
            keyField.text = NewApiPet.configApiKey
            intervalField.text = NewApiPet.configIntervalText
            dialog.currency = NewApiPet.configCurrency
            perUnitField.text = NewApiPet.configQuotaPerUnitText
            rateField.text = NewApiPet.configCnyRateText
            imageField.text = NewApiPet.configPetImage
            dialog.balanceSource = NewApiPet.balanceSource
            accountIntervalField.text = NewApiPet.configAccountIntervalText
        }
        errorText.text = ""
        x = Math.max(0, Screen.desktopAvailableWidth / 2 - width / 2)
        y = Math.max(0, Screen.desktopAvailableHeight / 2 - height / 2)
        visible = true
        if (manualMode) baseField.focusInput()
    }

    function save() {
        if (!petReady) return
        var ok = NewApiPet.saveSettings(
            baseField.text, keyField.text, intervalField.text, dialog.currency,
            perUnitField.text, rateField.text, imageField.text, dialog.source,
            dialog.balanceSource, accountIntervalField.text)
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
            id: formColumn
            objectName: "settingsFormColumn"
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

            // ------------------------------------------------ 凭证来源选择
            Text {
                text: "凭证来源"
                font.pixelSize: 11
                color: "#8A93A6"
            }
            Flow {
                width: parent.width
                spacing: 6

                Repeater {
                    model: [
                        { "id": "auto", "label": "自动复用", "hasKey": false },
                        { "id": "codex", "label": "Codex", "hasKey": false },
                        { "id": "claude", "label": "Claude", "hasKey": false },
                        { "id": "manual", "label": "手动", "hasKey": false }
                    ]

                    delegate: Rectangle {
                        id: chip
                        readonly property bool available: modelData.id === "auto"
                                                          || modelData.id === "manual"
                                                          || _sourceAvailable(modelData.id)
                        width: chipRow.implicitWidth + 24
                        height: 30
                        radius: 15
                        color: dialog.source === modelData.id ? "#3E5BD8" : "#FFFFFF"
                        border.color: dialog.source === modelData.id ? "#3E5BD8" : "#C9D3EC"
                        opacity: available ? 1.0 : 0.5

                        Row {
                            id: chipRow
                            anchors.centerIn: parent
                            spacing: 5
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.label
                                font.pixelSize: 12
                                color: dialog.source === modelData.id ? "#FFFFFF" : "#5B6478"
                            }
                            Rectangle {
                                visible: modelData.id !== "auto" && modelData.id !== "manual"
                                width: 7; height: 7; radius: 4
                                color: _sourceHasKey(modelData.id) ? "#3FB950" : "#C9D3EC"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: chip.available
                            cursorShape: Qt.PointingHandCursor
                            onClicked: dialog.source = modelData.id
                        }
                    }
                }
            }

            // 复用信息行
            Rectangle {
                width: parent.width
                height: 34
                radius: 8
                visible: !dialog.manualMode
                color: "#EDF2FF"
                border.color: "#D9E1F5"
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: dialog.selectedSite.length > 0
                          ? "复用 " + dialog.selectedLabel + "：" + dialog.selectedSite
                          : "复用 " + dialog.selectedLabel + "：未检测到可用配置，可切换到手动"
                    font.pixelSize: 11
                    color: "#3E5BD8"
                    elide: Text.ElideRight
                }
            }

            LabeledField {
                id: baseField
                width: parent.width
                fieldEnabled: dialog.manualMode
                label: "接口地址(new-api 站点根地址)"
                placeholder: "https://api.example.com"
            }

            LabeledField {
                id: keyField
                width: parent.width
                fieldEnabled: dialog.manualMode
                label: "API Key(手动模式;复用来源时忽略)"
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

            // ------------------------------------------------ 余额口径
            Column {
                width: parent.width
                spacing: 4

                Text {
                    text: "余额口径（大数字显示哪一套额度）"
                    font.pixelSize: 11
                    color: "#8A93A6"
                }
                Row {
                    spacing: 6

                    Repeater {
                        model: dialog.balanceOptions

                        delegate: Rectangle {
                            width: balanceChipRow.implicitWidth + 24
                            height: 28
                            radius: 14
                            color: dialog.balanceSource === modelData.id ? "#3E5BD8" : "#FFFFFF"
                            border.color: dialog.balanceSource === modelData.id ? "#3E5BD8" : "#C9D3EC"

                            Row {
                                id: balanceChipRow
                                anchors.centerIn: parent
                                spacing: 5

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    font.pixelSize: 11
                                    color: dialog.balanceSource === modelData.id ? "#FFFFFF" : "#5B6478"
                                }
                                Rectangle {
                                    visible: modelData.id === "account"
                                    width: 7; height: 7; radius: 4
                                    color: petReady && NewApiPet.accountReady ? "#3FB950" : "#C9D3EC"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: dialog.balanceSource = modelData.id
                            }
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: petReady && NewApiPet.accountReady
                          ? ("当前生效：" + NewApiPet.primaryBalanceCaption + " "
                             + NewApiPet.primaryBalanceText + " · 账户已用 " + NewApiPet.accountUsedText)
                          : "账户余额未就绪：需站点关闭「显示 Token 统计信息」后才会返回钱包余额"
                    font.pixelSize: 10
                    color: petReady && NewApiPet.accountReady ? "#5B6478" : "#B0762B"
                    wrapMode: Text.Wrap
                }
            }

            LabeledField {
                id: accountIntervalField
                objectName: "accountIntervalField"
                width: parent.width
                label: "账户余额轮询间隔(秒,30-7200;变化慢,建议 300)"
                placeholder: "300"
                validator: RegularExpressionValidator { regularExpression: /[0-9]+/ }
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
        }
    }

    function _sourceAvailable(id) {
        for (var i = 0; i < sources.length; ++i) {
            if (sources[i].id === id) return sources[i].site.length > 0
        }
        return false
    }

    function _sourceHasKey(id) {
        for (var i = 0; i < sources.length; ++i) {
            if (sources[i].id === id) return sources[i].hasKey
        }
        return false
    }

    // ---------------------------------------------------------------- 输入框组件
    component LabeledField: Column {
        id: fieldRoot

        property alias label: labelText.text
        property alias text: input.text
        property alias placeholder: hint.text
        property alias validator: input.validator
        property bool invalid: false
        property bool fieldEnabled: true

        function focusInput() { if (fieldEnabled) input.forceActiveFocus() }

        spacing: 4
        opacity: fieldEnabled ? 1.0 : 0.55

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
            color: fieldRoot.fieldEnabled ? "#FFFFFF" : "#EEF1F8"
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
                enabled: fieldRoot.fieldEnabled
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
