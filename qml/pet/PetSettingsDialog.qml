// 余额监控桌宠的设置窗口:优先复用 Codex/Claude 已配好的接口与 Key。
//
// PrismQML 组件清单:
//   卡片表面 Fluent.ShadowedRectangle / 分组 Fluent.SettingsCardGroup /
//   枚举项 Fluent.SettingsCard / 单选芯片 Fluent.Chip / 文本 Fluent.Label /
//   文本输入 Fluent.LineEdit / 数值输入 Fluent.SpinBox / 正文滚动 Fluent.ScrollArea /
//   分隔线 Fluent.Separator / 操作按钮 Fluent.Button / 关闭钮 Fluent.CloseButton;
//   配色与尺寸全部走 Fluent.Enums 令牌。
//
// 窗口壳为什么仍是裸 Window:桌宠在独立进程(pet_main.py)里也要能弹出这个设置窗,
// 它必须是无边框置顶工具窗;Fluent.WindowsCore 需要一个 PrismQML 主窗作为宿主,
// 而独立模式下根本没有宿主窗,所以保留裸 Window,表面交给 ShadowedRectangle。
//
// 表单长度已超过窗口高度,因此正文放进 Fluent.ScrollArea:加字段不再需要
// 同步改窗口高度(旧实现靠"字段总高必须小于窗口高"这条人工约定维持)。
import QtQuick
import QtQuick.Layouts
import QtQuick.Window

import PrismQML as Fluent

Window {
    id: dialog

    // ---------------------------------------------------------------- 基础窗口
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: Fluent.Enums.transparent
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

    // 对话框底色与边框:复用框架对话框的取色公式(皮肤感知)。
    readonly property color dialogBg: Fluent.Enums.hasOutlinedSurfaces
                                      ? Fluent.Enums.dialogColor
                                      : Fluent.Enums.dialogColors.containerBg
    readonly property color dialogBorder: Fluent.Enums.dialogColors.border

    // 枚举值 ↔ 下拉框索引映射:业务侧用字符串,下拉框用索引。
    readonly property var sourceValues: ["auto", "codex", "claude", "manual"]
    readonly property var sourceLabels: ["自动复用", "Codex", "Claude", "手动"]
    readonly property var currencyValues: ["auto", "CNY", "USD", "TOKENS"]
    readonly property var currencyLabels: ["跟随站点", "CNY", "USD", "TOKENS"]

    // 余额口径:自动 / 令牌额度 / 账户余额(账户余额要求站点关闭 DisplayTokenStatEnabled)
    // 用芯片而不是下拉框:三种口径要同时可见,且要配一行"当前生效"说明。
    readonly property var balanceOptions: [
        { "id": "auto", "label": "自动" },
        { "id": "token", "label": "令牌额度" },
        { "id": "account", "label": "账户余额" }
    ]

    // 桌宠形象候选:老的自绘矢量形体 + resources/pet 里随程序发布的 Q 版立绘。
    readonly property var imageChoices: {
        var choices = [{ "token": "vector", "label": "自绘小飞宠" }]
        if (petReady) {
            var presets = NewApiPet.petImagePresets
            for (var i = 0; i < presets.length; ++i) {
                if (presets[i].exists) {
                    choices.push({ "token": presets[i].token, "label": presets[i].label })
                }
            }
        }
        return choices
    }
    // 路径框当前值归一化:留空表示"用清单里的默认立绘",芯片才能正确高亮。
    readonly property string activeImageToken: {
        var raw = imageField.text.trim()
        if (raw === "") return petReady ? NewApiPet.defaultPetImageToken : ""
        return raw
    }
    // 预览走后端解析(支持 preset 令牌与用户自备绝对路径),不落盘。
    readonly property string petImagePreviewPath:
            petReady ? NewApiPet.resolvePetImage(imageField.text) : ""

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

    function _indexOf(values, value) {
        var index = values.indexOf(value)
        return index < 0 ? 0 : index
    }

    // 数值回填:空串/非法值退回默认值,再用控件自己的上下限夹住,
    // 保证"界面上看到的数字"就是要保存的数字(范围只在 SpinField 上定义一次)。
    function _fillSpin(field, text, fallback) {
        var raw = (text === undefined || text === null) ? "" : String(text).trim()
        var value = raw === "" ? fallback : Number(raw)
        if (!isFinite(value)) value = fallback
        field.value = Math.min(field.maximum, Math.max(field.minimum, value))
    }

    function openForEdit() {
        if (petReady) {
            dialog.source = NewApiPet.currentSource
            dialog.sources = NewApiPet.petSources
            baseField.text = NewApiPet.configBaseUrl
            keyField.text = NewApiPet.configApiKey
            dialog._fillSpin(intervalField, NewApiPet.configIntervalText, 60)
            dialog.currency = NewApiPet.configCurrency
            dialog._fillSpin(perUnitField, NewApiPet.configQuotaPerUnitText, 500000)
            dialog._fillSpin(rateField, NewApiPet.configCnyRateText, 7.3)
            imageField.text = NewApiPet.configPetImage
            dialog.balanceSource = NewApiPet.balanceSource
            dialog._fillSpin(accountIntervalField, NewApiPet.configAccountIntervalText, 300)
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
            baseField.text, keyField.text,
            String(Math.round(intervalField.value)), dialog.currency,
            String(perUnitField.value), String(rateField.value),
            imageField.text, dialog.source,
            dialog.balanceSource, String(Math.round(accountIntervalField.value)))
        if (ok) {
            visible = false
            return
        }
        errorText.text = NewApiPet.saveErrorText
    }

    function _sourceAvailable(id) {
        for (var i = 0; i < sources.length; ++i) {
            if (sources[i].id === id) return sources[i].site.length > 0
        }
        return false
    }

    // ---------------------------------------------------------------- 内容
    Fluent.ShadowedRectangle {
        id: card
        anchors.fill: parent
        // 留出投影空间:窗口本身是透明的,卡片贴边会把阴影裁掉。
        anchors.margins: Fluent.Enums.spacing.m
        radius: Fluent.Enums.radius.xlarge
        color: dialog.dialogBg
        border.color: dialog.dialogBorder
        border.width: Fluent.Enums.border.thin
        shadowLevel: Fluent.Enums.shadow.level4

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Fluent.Enums.spacing.xl
            spacing: Fluent.Enums.spacing.l

            // ------------------------------------------------ 标题行(可拖动)
            Item {
                id: titleBar
                objectName: "settingsTitleBar"
                Layout.fillWidth: true
                Layout.preferredHeight: Fluent.Enums.controlSize.buttonHeight

                // 无边框窗口的拖动:用框架的 Fluent.WindowDragHandle,它内部走
                // Qt 6 的 Window.startSystemMove(),交给系统接管拖动,避免手算
                // mouse delta 在多 DPI / Qt.Tool 窗口下的闪回与漂移。
                // 必须声明在 CloseButton 之前:手柄贴底层,关闭按钮留在上层截住
                // 自己的点击(否则点关闭会被当成拖动的起始按下)。
                Fluent.WindowDragHandle {
                    objectName: "settingsDragHandle"
                    anchors.fill: parent
                }

                Fluent.Label {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "余额监控设置"
                    type: Fluent.Enums.label.type_subtitle
                    font.pixelSize: Fluent.Enums.typography.bodyLarge
                    customTextColor: Fluent.Enums.foregroundColor
                }
                Fluent.CloseButton {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: dialog.visible = false
                }
            }

            Fluent.Separator {
                Layout.fillWidth: true
            }

            // ------------------------------------------------ 表单(可滚动)
            Fluent.ScrollArea {
                id: settingsScrollArea
                objectName: "settingsScrollArea"
                Layout.fillWidth: true
                Layout.fillHeight: true
                alwaysShowScrollBar: false

                Column {
                    id: formColumn
                    objectName: "settingsFormColumn"
                    width: parent ? parent.width : 0
                    spacing: Fluent.Enums.spacing.xl

                    // ============================================ 凭证来源
                    Fluent.SettingsCardGroup {
                        width: parent.width
                        title: "凭证来源"
                        spacing: Fluent.Enums.spacing.xxs

                        Fluent.SettingsCard {
                            width: parent ? parent.width : 0
                            title: "复用来源"
                            // 卡片内的副标题宽度被右侧下拉框挤掉,只放最短的状态词;
                            // 完整的来源地址由下方整行说明给出,不会被截断。
                            content: dialog.manualMode
                                     ? "手动填写"
                                     : (dialog.selectedSite.length > 0 ? "已检测到配置" : "未检测到配置")
                            type: Fluent.Enums.settingCard.type_combobox
                            model: dialog.sourceLabels
                            placeholderText: "选择凭证来源"
                            currentIndex: dialog._indexOf(dialog.sourceValues, dialog.source)
                            onIndexSelected: function (index) {
                                dialog.source = dialog.sourceValues[index]
                            }
                        }

                        Fluent.SettingsCard {
                            width: parent ? parent.width : 0
                            title: "额度展示类型"
                            content: dialog.currency === "auto" ? "跟随站点" : "覆盖站点单位"
                            type: Fluent.Enums.settingCard.type_combobox
                            model: dialog.currencyLabels
                            placeholderText: "选择额度展示类型"
                            currentIndex: dialog._indexOf(dialog.currencyValues, dialog.currency)
                            onIndexSelected: function (index) {
                                dialog.currency = dialog.currencyValues[index]
                            }
                        }

                        Fluent.Label {
                            objectName: "sourceDetail"
                            width: parent ? parent.width : 0
                            text: dialog.manualMode
                                  ? "手动填写接口地址与 API Key"
                                  : (dialog.selectedSite.length > 0
                                     ? "复用 " + dialog.selectedLabel + "：" + dialog.selectedSite
                                     : "未检测到可用配置，可切换到手动")
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.captionCompact
                            customTextColor: Fluent.Enums.tertiaryForeground
                            elide: Text.ElideMiddle
                        }

                        Fluent.Label {
                            width: parent ? parent.width : 0
                            visible: dialog.currency === "auto"
                            text: "额度单位跟随站点：" + (petReady ? NewApiPet.resolvedCurrency : "—")
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.captionCompact
                            customTextColor: Fluent.Enums.tertiaryForeground
                        }
                    }

                    // ============================================ 接口凭证
                    Fluent.SettingsCardGroup {
                        width: parent.width
                        title: "接口凭证"
                        spacing: Fluent.Enums.spacing.xs

                        LabeledField {
                            id: baseField
                            objectName: "baseField"
                            width: parent.width
                            fieldEnabled: dialog.manualMode
                            label: "接口地址（new-api 站点根地址）"
                            placeholder: "https://api.example.com"
                        }

                        LabeledField {
                            id: keyField
                            objectName: "keyField"
                            width: parent.width
                            fieldEnabled: dialog.manualMode
                            label: "API Key（手动模式；复用来源时忽略）"
                            placeholder: "sk-..."
                        }
                    }

                    // ============================================ 轮询与换算
                    Fluent.SettingsCardGroup {
                        width: parent.width
                        title: "轮询与换算"
                        spacing: Fluent.Enums.spacing.xs

                        SpinField {
                            id: intervalField
                            objectName: "intervalField"
                            width: parent.width
                            label: "轮询间隔（秒，5-3600）"
                            minimum: 5
                            maximum: 3600
                        }

                        SpinField {
                            id: accountIntervalField
                            objectName: "accountIntervalField"
                            width: parent.width
                            label: "账户余额轮询间隔（秒，30-7200；变化慢，建议 300）"
                            minimum: 30
                            maximum: 7200
                        }

                        SpinField {
                            id: perUnitField
                            objectName: "perUnitField"
                            width: parent.width
                            label: "$ 对应额度（默认 500000）"
                            minimum: 0.01
                            maximum: 1000000000000
                            doubleValue: true
                        }

                        SpinField {
                            id: rateField
                            objectName: "rateField"
                            width: parent.width
                            label: "USD→CNY 汇率（默认 7.3）"
                            minimum: 0.001
                            maximum: 10000
                            doubleValue: true
                        }
                    }

                    // ============================================ 余额口径
                    Fluent.SettingsCardGroup {
                        width: parent.width
                        title: "余额口径"
                        spacing: Fluent.Enums.spacing.xs

                        Fluent.Label {
                            width: parent ? parent.width : 0
                            text: "大数字显示哪一套额度"
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.captionCompact
                            customTextColor: Fluent.Enums.tertiaryForeground
                        }

                        Item {
                            width: parent ? parent.width : 0
                            height: balanceRow.height

                            Row {
                                id: balanceRow
                                width: parent.width
                                spacing: Fluent.Enums.spacing.s

                                Repeater {
                                    model: dialog.balanceOptions

                                    delegate: Fluent.Chip {
                                        text: modelData.label
                                        // 单选语义,同凭证来源;账户是否就绪由下方提示行说明
                                        checkable: false
                                        closable: false
                                        checked: dialog.balanceSource === modelData.id
                                        onClicked: dialog.balanceSource = modelData.id
                                    }
                                }
                            }
                        }

                        Fluent.Label {
                            objectName: "balanceHint"
                            width: parent ? parent.width : 0
                            text: petReady && NewApiPet.accountReady
                                  ? ("当前生效：" + NewApiPet.primaryBalanceCaption + " "
                                     + NewApiPet.primaryBalanceText + " · 账户已用 " + NewApiPet.accountUsedText)
                                  : "账户余额未就绪：需站点关闭「显示 Token 统计信息」后才会返回钱包余额"
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.micro
                            customTextColor: petReady && NewApiPet.accountReady
                                             ? Fluent.Enums.secondaryForeground
                                             : Fluent.Enums.statusLevel.warningColor
                            wrapMode: Text.WordWrap
                        }
                    }

                    // ============================================ 桌宠外观
                    Fluent.SettingsCardGroup {
                        width: parent.width
                        title: "桌宠外观"
                        spacing: Fluent.Enums.spacing.xs

                        // 左预览右单选;点芯片只是把令牌写进下面的路径框,
                        // 路径框仍是唯一提交值(自备图片的老用法不变)。
                        RowLayout {
                            width: parent.width
                            spacing: Fluent.Enums.spacing.m

                            Rectangle {
                                objectName: "petImagePreview"
                                Layout.preferredWidth: 64
                                Layout.preferredHeight: 64
                                Layout.alignment: Qt.AlignVCenter
                                radius: 10
                                color: Fluent.Enums.dialogColors.containerBg
                                border.color: Fluent.Enums.dialogColors.border
                                border.width: 1
                                visible: dialog.petImagePreviewPath !== ""

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 5
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                    mipmap: true
                                    source: dialog.petImagePreviewPath !== ""
                                            ? "file:///" + dialog.petImagePreviewPath.replace(/\\/g, "/") : ""
                                }
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: Fluent.Enums.spacing.s

                                Repeater {
                                    model: dialog.imageChoices

                                    delegate: Fluent.Chip {
                                        text: modelData.label
                                        // 单选语义:选中即把令牌写回路径框
                                        checkable: false
                                        closable: false
                                        checked: dialog.activeImageToken === modelData.token
                                        onClicked: imageField.text = modelData.token
                                    }
                                }
                            }
                        }

                        LabeledField {
                            id: imageField
                            objectName: "imageField"
                            width: parent.width
                            label: "桌宠图片路径（可选，留空使用内置形象）"
                            placeholder: "D:\\pictures\\pet.png"
                        }
                    }

                    Fluent.Label {
                        id: errorText
                        width: parent ? parent.width : 0
                        text: ""
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.captionCompact
                        customTextColor: Fluent.Enums.statusLevel.errorColor
                        wrapMode: Text.WrapAnywhere
                        visible: text !== ""
                    }

                    // 底部留白:让最后一张卡片不贴着滚动区边缘
                    Item {
                        width: 1
                        height: Fluent.Enums.spacing.m
                    }
                }
            }

            Fluent.Separator {
                Layout.fillWidth: true
            }

            // ------------------------------------------------ 操作按钮
            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignRight
                spacing: Fluent.Enums.spacing.l

                Fluent.Button {
                    Layout.preferredWidth: 88
                    style: Fluent.Enums.button.style_default
                    text: "取消"
                    onClicked: dialog.visible = false
                }

                Fluent.Button {
                    Layout.preferredWidth: 112
                    style: Fluent.Enums.button.style_primary
                    text: "保存并刷新"
                    onClicked: dialog.save()
                }
            }
        }
    }

    // ---------------------------------------------------------------- 字段组件
    // 标签用 Fluent.Label,输入框用框架的 Fluent.LineEdit:焦点描边/占位符/禁用态
    // 都由框架接管,回车即保存。
    component LabeledField: Column {
        id: fieldRoot

        property alias label: labelText.text
        property alias text: field.text
        property alias placeholder: field.placeholderText
        property alias validator: field.validator
        property bool fieldEnabled: true

        function focusInput() { if (fieldEnabled) field.forceActiveFocus() }

        spacing: Fluent.Enums.spacing.xs
        opacity: fieldEnabled ? Fluent.Enums.opacityLevel.visible
                              : Fluent.Enums.opacityLevel.secondary

        Fluent.Label {
            id: labelText
            type: Fluent.Enums.label.type_caption
            font.pixelSize: Fluent.Enums.typography.captionCompact
            customTextColor: Fluent.Enums.tertiaryForeground
        }

        Fluent.LineEdit {
            id: field
            width: parent.width
            enabled: fieldRoot.fieldEnabled
            clearButtonEnabled: false
            onAccepted: dialog.save()
        }
    }

    // 数值字段用框架的 Fluent.SpinBox:上下限与后端校验边界保持一致,
    // 越界输入由控件自己夹住,不再只把范围写在标签文字里。
    component SpinField: Column {
        id: spinRoot

        property alias label: spinLabel.text
        property alias value: spinField.value
        property alias minimum: spinField.minimum
        property alias maximum: spinField.maximum
        property bool fieldEnabled: true
        property bool doubleValue: false

        function focusInput() { if (fieldEnabled) spinField.forceActiveFocus() }

        spacing: Fluent.Enums.spacing.xs
        opacity: fieldEnabled ? Fluent.Enums.opacityLevel.visible
                              : Fluent.Enums.opacityLevel.secondary

        Fluent.Label {
            id: spinLabel
            type: Fluent.Enums.label.type_caption
            font.pixelSize: Fluent.Enums.typography.captionCompact
            customTextColor: Fluent.Enums.tertiaryForeground
        }

        Fluent.SpinBox {
            id: spinField
            width: parent.width
            enabled: spinRoot.fieldEnabled
            type: spinRoot.doubleValue ? Fluent.Enums.input.spinbox_double
                                       : Fluent.Enums.input.spinbox_normal
        }
    }
}
