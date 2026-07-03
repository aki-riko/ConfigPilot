// Codex 配置页
import QtQuick
import QtQuick.Window
import PrismQML as Fluent

Item {
    id: root

    // 当前在输入框里的待应用值(初始化为 config 现值)
    property string fProvider: ""
    property string fBaseUrl: ""
    property string fWireApi: ""
    property string fModel: ""
    // 高级字段
    property bool fRequiresAuth: false
    property string fReasoningEffort: ""
    property bool fDisableStorage: false
    property string fContextWindow: ""
    property string fAutoCompactLimit: ""
    property string fToolOutputLimit: ""
    readonly property real contextWindowNumber: parsePositive(fContextWindow)
    readonly property real autoCompactNumber: parsePositive(fAutoCompactLimit)
    readonly property real compactRatio: contextWindowNumber > 0 && autoCompactNumber > 0
                                         ? Math.min(1, autoCompactNumber / contextWindowNumber)
                                         : 0

    function parsePositive(value) {
        var n = Number(value)
        return isFinite(n) && n > 0 ? n : 0
    }

    function compactRatioText() {
        if (contextWindowNumber <= 0 || autoCompactNumber <= 0) return "未设置"
        return Math.round((autoCompactNumber / contextWindowNumber) * 1000) / 10 + "%"
    }

    function useGpt55LongContext() {
        fModel = "gpt-5.5"
        fContextWindow = "1050000"
        fAutoCompactLimit = "900000"
        fToolOutputLimit = "6000"
    }

    function syncFromConfig() {
        fProvider = (CodexConfig && CodexConfig.provider) || "relay"
        fBaseUrl  = (CodexConfig && CodexConfig.baseUrl) || ""
        fWireApi  = (CodexConfig && CodexConfig.wireApi) || "responses"
        fModel    = (CodexConfig && CodexConfig.model) || ""
        fRequiresAuth    = CodexConfig ? CodexConfig.requiresAuth : false
        fReasoningEffort = (CodexConfig && CodexConfig.reasoningEffort) || ""
        fDisableStorage  = CodexConfig ? CodexConfig.disableStorage : false
        fContextWindow = (CodexConfig && CodexConfig.modelContextWindow) || ""
        fAutoCompactLimit = (CodexConfig && CodexConfig.modelAutoCompactTokenLimit) || ""
        fToolOutputLimit = (CodexConfig && CodexConfig.toolOutputTokenLimit) || ""
    }
    Component.onCompleted: syncFromConfig()

    Connections {
        target: CodexConfig
        function onNotify(level, title, msg) {
            var host = (root.Window.window ? root.Window.window.contentItem : root)
            var ib = Fluent.NotificationManager.infoBar
            var fn = level === 1 ? ib.success
                   : level === 2 ? ib.warning
                   : level === 3 ? ib.error
                                 : ib.info
            fn(host, title, msg, Fluent.Enums.duration.notification,
               Fluent.NotificationManager.posTop)
        }
        function onChanged() { root.syncFromConfig() }
    }

    Fluent.ScrollArea {
        anchors.fill: parent

        Column {
            id: pageColumn
            width: parent ? parent.width : 0
            spacing: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.xxxl

            // 页面标题
            Column {
                width: parent ? parent.width : 0
                spacing: Fluent.Enums.spacing.xs
                Text {
                    text: "Codex 配置"
                    font.pixelSize: Fluent.Enums.typography.displayLarge
                    font.bold: true
                    color: Fluent.Enums.textColor.primary
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    text: CodexConfig ? CodexConfig.configPath : ""
                    font.pixelSize: Fluent.Enums.typography.caption
                    color: Fluent.Enums.textColor.tertiary
                    font.family: Fluent.Enums.fontFamily
                }
            }

            //__SELECT_CARD__
            Fluent.Card {
                width: parent ? parent.width : 0
                autoHeight: true

                Column {
                    width: parent ? parent.width : 0
                    leftPadding: Fluent.Enums.spacing.l
                    rightPadding: Fluent.Enums.spacing.l
                    topPadding: Fluent.Enums.spacing.l
                    bottomPadding: Fluent.Enums.spacing.l
                    spacing: Fluent.Enums.spacing.m

                    Text {
                        text: "选择中转"
                        font.pixelSize: Fluent.Enums.typography.subtitle
                        font.bold: true
                        color: Fluent.Enums.textColor.primary
                        font.family: Fluent.Enums.fontFamily
                    }

                    // 预置中转下拉:选中后填入下方各字段
                    Fluent.ComboBoxDefault {
                        id: presetBox
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        property var presetList: CodexConfig ? CodexConfig.presets : []
                        model: {
                            var arr = []
                            for (var i = 0; i < presetList.length; i++) arr.push(presetList[i].name)
                            arr.push("自定义…")
                            return arr
                        }
                        onActivated: function(index) {
                            if (index >= 0 && index < presetList.length) {
                                var p = presetList[index]
                                root.fBaseUrl = p.baseUrl
                                root.fProvider = p.provider
                                root.fWireApi = p.wireApi
                                root.fModel = p.model
                            }
                            // 选「自定义…」则不改字段,留用户手填
                        }
                    }

                    //__FIELDS__
                    // base_url(主字段)
                    Text {
                        text: "base_url"
                        font.pixelSize: Fluent.Enums.typography.body
                        color: Fluent.Enums.textColor.secondary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Fluent.LineEdit {
                        id: baseUrlEdit
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        placeholderText: "https://api.example.com/v1"
                        Component.onCompleted: text = root.fBaseUrl
                        onTextChanged: if (text !== root.fBaseUrl) root.fBaseUrl = text
                        Connections {
                            target: root
                            function onFBaseUrlChanged() {
                                if (baseUrlEdit.text !== root.fBaseUrl) baseUrlEdit.text = root.fBaseUrl
                            }
                        }
                    }

                    // 高级项(provider / wire_api / model)
                    Item { width: 1; height: Fluent.Enums.spacing.xs }
                    Text {
                        text: "高级"
                        font.pixelSize: Fluent.Enums.typography.caption
                        color: Fluent.Enums.textColor.tertiary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Grid {
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        columns: 2
                        rowSpacing: Fluent.Enums.spacing.s
                        columnSpacing: Fluent.Enums.spacing.m
                        verticalItemAlignment: Grid.AlignVCenter

                        Text { text: "provider"; width: 80; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                        Fluent.LineEdit {
                            id: providerEdit
                            width: 240
                            Component.onCompleted: text = root.fProvider
                            onTextChanged: if (text !== root.fProvider) root.fProvider = text
                            Connections {
                                target: root
                                function onFProviderChanged() {
                                    if (providerEdit.text !== root.fProvider) providerEdit.text = root.fProvider
                                }
                            }
                        }
                        Text { text: "wire_api"; width: 80; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                        Fluent.LineEdit {
                            id: wireApiEdit
                            width: 240
                            Component.onCompleted: text = root.fWireApi
                            onTextChanged: if (text !== root.fWireApi) root.fWireApi = text
                            Connections {
                                target: root
                                function onFWireApiChanged() {
                                    if (wireApiEdit.text !== root.fWireApi) wireApiEdit.text = root.fWireApi
                                }
                            }
                        }
                        Text { text: "model"; width: 80; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                        Row {
                            spacing: Fluent.Enums.spacing.s
                            Fluent.LineEdit {
                                id: modelEdit
                                width: 200
                                placeholderText: "模型名,或从右侧下拉选"
                                Component.onCompleted: text = root.fModel
                                onTextChanged: if (text !== root.fModel) root.fModel = text
                                Connections {
                                    target: root
                                    function onFModelChanged() {
                                        if (modelEdit.text !== root.fModel) modelEdit.text = root.fModel
                                    }
                                }
                            }
                            // 只读下拉:获取到的模型,选中写进 modelEdit
                            Fluent.ComboBoxDefault {
                                id: modelPicker
                                width: 150
                                placeholderText: "已获取模型"
                                model: CodexConfig ? CodexConfig.availableModels : []
                                onActivated: function(index) {
                                    var arr = CodexConfig ? CodexConfig.availableModels : []
                                    if (index >= 0 && index < arr.length) root.fModel = arr[index]
                                }
                            }
                            Fluent.Button {
                                style: Fluent.Enums.button.style_default
                                text: "获取模型"
                                onClicked: if (CodexConfig) CodexConfig.fetchModels(root.fBaseUrl, keyInput.text)
                            }
                        }
                    }

                    // 高级开关与思考等级
                    Fluent.Toggle {
                        id: authToggle
                        controlType: Fluent.Enums.toggle.control_switch
                        type: Fluent.Enums.toggle.type_subtitle
                        text: "需要本地路由映射 (requires_openai_auth)"
                        subtitle: "供应商用 Chat Completions 协议或非 GPT 模型(DeepSeek/Kimi)时开启"
                        Component.onCompleted: checked = root.fRequiresAuth
                        onToggled: function(c) { root.fRequiresAuth = c }
                        Connections {
                            target: root
                            function onFRequiresAuthChanged() {
                                if (authToggle.checked !== root.fRequiresAuth) authToggle.checked = root.fRequiresAuth
                            }
                        }
                    }
                    Fluent.Toggle {
                        id: storageToggle
                        controlType: Fluent.Enums.toggle.control_switch
                        type: Fluent.Enums.toggle.type_subtitle
                        text: "禁用响应存储 (disable_response_storage)"
                        subtitle: "不在服务端保留响应,部分第三方中转需要"
                        Component.onCompleted: checked = root.fDisableStorage
                        onToggled: function(c) { root.fDisableStorage = c }
                        Connections {
                            target: root
                            function onFDisableStorageChanged() {
                                if (storageToggle.checked !== root.fDisableStorage) storageToggle.checked = root.fDisableStorage
                            }
                        }
                    }
                    Row {
                        spacing: Fluent.Enums.spacing.m
                        Text {
                            text: "思考等级"
                            anchors.verticalCenter: parent.verticalCenter
                            color: Fluent.Enums.textColor.tertiary
                            font.pixelSize: Fluent.Enums.typography.body
                            font.family: Fluent.Enums.fontFamily
                        }
                        Fluent.ComboBoxDefault {
                            id: effortBox
                            width: 160
                            property var effortArr: ["", "low", "medium", "high", "xhigh"]
                            model: ["(不设置)", "low", "medium", "high", "xhigh"]
                            Component.onCompleted: currentIndex = Math.max(0, effortArr.indexOf(root.fReasoningEffort))
                            onActivated: function(index) {
                                root.fReasoningEffort = effortArr[index] || ""
                            }
                            Connections {
                                target: root
                                function onFReasoningEffortChanged() {
                                    var i = Math.max(0, effortBox.effortArr.indexOf(root.fReasoningEffort))
                                    if (effortBox.currentIndex !== i) effortBox.currentIndex = i
                                }
                            }
                        }
                    }

                    Item { width: 1; height: Fluent.Enums.spacing.xs }
                    Column {
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        spacing: Fluent.Enums.spacing.s

                        Row {
                            width: parent ? parent.width : 0
                            spacing: Fluent.Enums.spacing.m
                            Text {
                                text: "上下文预算"
                                anchors.verticalCenter: parent.verticalCenter
                                font.pixelSize: Fluent.Enums.typography.caption
                                color: Fluent.Enums.textColor.tertiary
                                font.family: Fluent.Enums.fontFamily
                            }
                            Text {
                                text: "自动压缩阈值占窗口 " + root.compactRatioText()
                                anchors.verticalCenter: parent.verticalCenter
                                font.pixelSize: Fluent.Enums.typography.caption
                                color: Fluent.Enums.textColor.secondary
                                font.family: Fluent.Enums.fontFamily
                            }
                        }

                        Rectangle {
                            width: parent ? parent.width : 0
                            height: 12
                            radius: 6
                            color: "#E5E7EB"
                            clip: true

                            Rectangle {
                                height: parent.height
                                radius: parent.radius
                                width: Math.max(0, Math.min(parent.width, parent.width * root.compactRatio))
                                color: root.compactRatio >= 0.8 ? "#16A34A" : "#2563EB"
                            }
                        }

                        Grid {
                            width: parent ? parent.width : 0
                            columns: 2
                            rowSpacing: Fluent.Enums.spacing.s
                            columnSpacing: Fluent.Enums.spacing.m
                            verticalItemAlignment: Grid.AlignVCenter

                            Text { text: "上下文窗口"; width: 190; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                            Fluent.LineEdit {
                                id: contextWindowEdit
                                width: 220
                                placeholderText: "1050000"
                                Component.onCompleted: text = root.fContextWindow
                                onTextChanged: if (text !== root.fContextWindow) root.fContextWindow = text
                                Connections {
                                    target: root
                                    function onFContextWindowChanged() {
                                        if (contextWindowEdit.text !== root.fContextWindow) contextWindowEdit.text = root.fContextWindow
                                    }
                                }
                            }

                            Text { text: "自动压缩阈值"; width: 190; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                            Fluent.LineEdit {
                                id: autoCompactEdit
                                width: 220
                                placeholderText: "900000"
                                Component.onCompleted: text = root.fAutoCompactLimit
                                onTextChanged: if (text !== root.fAutoCompactLimit) root.fAutoCompactLimit = text
                                Connections {
                                    target: root
                                    function onFAutoCompactLimitChanged() {
                                        if (autoCompactEdit.text !== root.fAutoCompactLimit) autoCompactEdit.text = root.fAutoCompactLimit
                                    }
                                }
                            }

                            Text { text: "工具输出保留"; width: 190; color: Fluent.Enums.textColor.tertiary; font.pixelSize: Fluent.Enums.typography.body; font.family: Fluent.Enums.fontFamily }
                            Fluent.LineEdit {
                                id: toolOutputEdit
                                width: 220
                                placeholderText: "6000"
                                Component.onCompleted: text = root.fToolOutputLimit
                                onTextChanged: if (text !== root.fToolOutputLimit) root.fToolOutputLimit = text
                                Connections {
                                    target: root
                                    function onFToolOutputLimitChanged() {
                                        if (toolOutputEdit.text !== root.fToolOutputLimit) toolOutputEdit.text = root.fToolOutputLimit
                                    }
                                }
                            }
                        }

                        Row {
                            spacing: Fluent.Enums.spacing.m
                            Fluent.Button {
                                style: Fluent.Enums.button.style_default
                                text: "套用 GPT-5.5 长上下文"
                                onClicked: root.useGpt55LongContext()
                            }
                            Fluent.Button {
                                style: Fluent.Enums.button.style_default
                                text: "清空"
                                onClicked: {
                                    root.fContextWindow = ""
                                    root.fAutoCompactLimit = ""
                                    root.fToolOutputLimit = ""
                                }
                            }
                        }
                    }

                    // 操作按钮
                    Row {
                        spacing: Fluent.Enums.spacing.m
                        topPadding: Fluent.Enums.spacing.xs
                        Fluent.Button {
                            style: Fluent.Enums.button.style_primary
                            text: "应用配置"
                            onClicked: if (CodexConfig) CodexConfig.applyConfig({
                                "baseUrl": root.fBaseUrl,
                                "provider": root.fProvider,
                                "wireApi": root.fWireApi,
                                "model": root.fModel,
                                "requiresAuth": root.fRequiresAuth,
                                "reasoningEffort": root.fReasoningEffort,
                                "disableStorage": root.fDisableStorage,
                                "modelContextWindow": root.fContextWindow,
                                "modelAutoCompactTokenLimit": root.fAutoCompactLimit,
                                "toolOutputTokenLimit": root.fToolOutputLimit
                            })
                        }
                        Fluent.Button {
                            style: Fluent.Enums.button.style_default
                            text: "重置为当前"
                            onClicked: root.syncFromConfig()
                        }
                        Fluent.Button {
                            style: Fluent.Enums.button.style_default
                            text: "重置为默认"
                            onClicked: if (CodexConfig) CodexConfig.resetDefault()
                        }
                    }
                }
            }

            //__KEY_CARD__
            Fluent.Card {
                width: parent ? parent.width : 0
                autoHeight: true

                Column {
                    width: parent ? parent.width : 0
                    leftPadding: Fluent.Enums.spacing.l
                    rightPadding: Fluent.Enums.spacing.l
                    topPadding: Fluent.Enums.spacing.l
                    bottomPadding: Fluent.Enums.spacing.l
                    spacing: Fluent.Enums.spacing.m

                    Row {
                        spacing: Fluent.Enums.spacing.s
                        Text {
                            text: "设置 API key"
                            font.pixelSize: Fluent.Enums.typography.subtitle
                            font.bold: true
                            color: Fluent.Enums.textColor.primary
                            font.family: Fluent.Enums.fontFamily
                        }
                        Text {
                            text: (CodexConfig && CodexConfig.hasKey) ? "(已设置)" : "(未设置)"
                            font.pixelSize: Fluent.Enums.typography.body
                            color: (CodexConfig && CodexConfig.hasKey) ? Fluent.Enums.statusLevel.successColor : Fluent.Enums.statusLevel.warningColor
                            font.family: Fluent.Enums.fontFamily
                        }
                    }
                    Fluent.LineEdit {
                        id: keyInput
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                        placeholderText: "粘贴 sk-... 后点保存(留空则不改动)"
                    }
                    Fluent.Button {
                        style: Fluent.Enums.button.style_filled
                        text: "保存 key"
                        onClicked: { if (CodexConfig) CodexConfig.setKey(keyInput.text); keyInput.text = "" }
                    }
                }
            }
        }
    }
}
