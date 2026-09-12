// 余额监控桌宠的设置窗口:优先复用 Codex/Claude 已配好的接口与 Key。
// 窗口壳保持无边框独立窗(桌宠在独立进程也要能弹出),表单控件全部用
// PrismQML 封装:Fluent.Chip 选择芯片 / Fluent.LineEdit 输入框 /
// Fluent.Button 操作按钮 / Fluent.CloseButton 关闭钮,深浅色跟随主题。
import QtQuick
import QtQuick.Window

import PrismQML as Fluent

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

    // 对话框底色与边框:复用框架对话框的取色公式(皮肤感知)。
    readonly property color dialogBg: Fluent.Enums.hasOutlinedSurfaces
                                      ? Fluent.Enums.dialogColor
                                      : Fluent.Enums.dialogColors.containerBg
    readonly property color dialogBorder: Fluent.Enums.dialogColors.border

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
        color: dialog.dialogBg
        border.color: dialog.dialogBorder

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
                    color: Fluent.Enums.foregroundColor
                }
                Fluent.CloseButton {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: dialog.visible = false
                }
            }

            // ------------------------------------------------ 凭证来源选择
            Text {
                text: "凭证来源"
                font.pixelSize: 11
                color: Fluent.Enums.tertiaryForeground
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

                    delegate: Fluent.Chip {
                        id: chip
                        readonly property bool available: modelData.id === "auto"
                                                          || modelData.id === "manual"
                                                          || _sourceAvailable(modelData.id)
                        text: modelData.label
                        // 单选语义:选中态由 source 派生,不让芯片内部翻转(checkable:false),
                        // 否则点已选中项会把它翻成未选并打断 checked 绑定。
                        checkable: false
                        closable: false
                        checked: dialog.source === modelData.id
                        enabled: chip.available
                        opacity: chip.available ? 1.0 : 0.5
                        onClicked: dialog.source = modelData.id
                    }
                }
            }

            // 复用信息行
            Rectangle {
                width: parent.width
                height: 34
                radius: 8
                visible: !dialog.manualMode
                color: Qt.alpha(Fluent.Enums.accentColor, 0.10)
                border.color: Qt.alpha(Fluent.Enums.accentColor, 0.25)
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
                    color: Fluent.Enums.accentColor
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
                        color: Fluent.Enums.tertiaryForeground
                    }
                    Row {
                        spacing: 6

                        Repeater {
                            model: [
                                { "id": "auto", "label": "跟随站点" },
                                { "id": "CNY", "label": "CNY" },
                                { "id": "USD", "label": "USD" },
                                { "id": "TOKENS", "label": "TOKENS" }
                            ]

                            delegate: Fluent.Chip {
                                text: modelData.label
                                // 单选语义,同凭证来源芯片
                                checkable: false
                                closable: false
                                checked: dialog.currency === modelData.id
                                onClicked: dialog.currency = modelData.id
                            }
                        }
                    }
                    Text {
                        text: dialog.currency === "auto" && petReady
                              ? "当前跟随站点：" + NewApiPet.resolvedCurrency : ""
                        font.pixelSize: 10
                        color: Fluent.Enums.tertiaryForeground
                        visible: text !== ""
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
                    color: Fluent.Enums.tertiaryForeground
                }
                Row {
                    spacing: 6

                    Repeater {
                        model: dialog.balanceOptions

                        delegate: Fluent.Chip {
                            text: modelData.label
                            // 单选语义,同凭证来源芯片;账户是否就绪由下方提示行说明
                            checkable: false
                            closable: false
                            checked: dialog.balanceSource === modelData.id
                            onClicked: dialog.balanceSource = modelData.id
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
                    color: petReady && NewApiPet.accountReady
                           ? Fluent.Enums.secondaryForeground
                           : Fluent.Enums.statusLevel.warningColor
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
                color: Fluent.Enums.statusLevel.errorColor
                wrapMode: Text.WrapAnywhere
                visible: text !== ""
            }

            Item { width: 1; height: 1 }

            Row {
                anchors.right: parent.right
                spacing: 10

                Fluent.Button {
                    width: 88
                    style: Fluent.Enums.button.style_default
                    text: "取消"
                    onClicked: dialog.visible = false
                }

                Fluent.Button {
                    width: 112
                    style: Fluent.Enums.button.style_primary
                    text: "保存并刷新"
                    onClicked: dialog.save()
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

    // ---------------------------------------------------------------- 输入框组件
    // 标签自绘(行高与原布局一致),输入框用框架的 Fluent.LineEdit:
    // 焦点描边/占位符/禁用态都由框架接管,回车即保存。
    component LabeledField: Column {
        id: fieldRoot

        property alias label: labelText.text
        property alias text: field.text
        property alias placeholder: field.placeholderText
        property alias validator: field.validator
        property bool fieldEnabled: true

        function focusInput() { if (fieldEnabled) field.forceActiveFocus() }

        spacing: 4
        opacity: fieldEnabled ? 1.0 : 0.55

        Text {
            id: labelText
            font.pixelSize: 11
            color: Fluent.Enums.tertiaryForeground
        }

        Fluent.LineEdit {
            id: field
            width: parent.width
            enabled: fieldRoot.fieldEnabled
            clearButtonEnabled: false
            onAccepted: dialog.save()
        }
    }
}
