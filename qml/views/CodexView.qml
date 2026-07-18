// Codex 配置页
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import PrismQML as Fluent

Item {
    id: root
    objectName: "codexView"

    property string fProvider: ""
    property string fBaseUrl: ""
    property string fWireApi: ""
    property string fModel: ""
    property bool fRequiresAuth: false
    property string fReasoningEffort: ""
    property bool fDisableStorage: false
    property string fContextWindow: ""
    property string fAutoCompactLimit: ""
    property string fToolOutputLimit: ""
    property string committedModel: ""
    readonly property bool configBusy: CodexConfig
                                               ? CodexConfig.operationBusy
                                               : false
    readonly property bool modelsLoading: CodexConfig
                                                ? CodexConfig.modelsLoading
                                                : false

    readonly property int pagePadding: width < 720
                                       ? Fluent.Enums.spacing.l
                                       : Fluent.Enums.spacing.xl
    readonly property var currentContextPreset: CodexConfig
                                                ? CodexConfig.stableContextPreset()
                                                : ({})
    readonly property real contextWindowNumber: parsePositive(fContextWindow)
    readonly property real autoCompactNumber: parsePositive(fAutoCompactLimit)
    readonly property real compactRatio: contextWindowNumber > 0 && autoCompactNumber > 0
                                         ? Math.min(1, autoCompactNumber / contextWindowNumber)
                                         : 0
    readonly property bool hasDraftChanges: {
        if (!CodexConfig) return false
        return fProvider !== (CodexConfig.provider || "relay")
            || fBaseUrl !== (CodexConfig.baseUrl || "")
            || fWireApi !== (CodexConfig.wireApi || "responses")
            || fModel !== (CodexConfig.model || "")
            || fRequiresAuth !== CodexConfig.requiresAuth
            || fReasoningEffort !== (CodexConfig.reasoningEffort || "")
            || fDisableStorage !== CodexConfig.disableStorage
            || fContextWindow !== (CodexConfig.modelContextWindow || "")
            || fAutoCompactLimit !== (CodexConfig.modelAutoCompactTokenLimit || "")
            || fToolOutputLimit !== (CodexConfig.toolOutputTokenLimit || "")
    }

    function parsePositive(value) {
        var numberValue = Number(value)
        return isFinite(numberValue) && numberValue > 0 ? numberValue : 0
    }

    function compactRatioLabel() {
        if (contextWindowNumber <= 0 || autoCompactNumber <= 0) return "未设置"
        return Math.round((autoCompactNumber / contextWindowNumber) * 1000) / 10 + "%"
    }

    function highestReasoningEffort(modelName) {
        if (!modelName || !modelName.trim()) return ""
        return CodexConfig
                ? CodexConfig.highestReasoningEffortForModel(modelName)
                : ""
    }

    function normalizedReasoningEffort(modelName, configuredValue) {
        if (!modelName || !modelName.trim()) return configuredValue || ""
        var options = CodexConfig
                      ? CodexConfig.reasoningOptionsForModel(modelName)
                      : []
        for (var i = 0; i < options.length; i++) {
            if (options[i].value === configuredValue) return configuredValue
        }
        return highestReasoningEffort(modelName)
    }

    function useModelContextPreset(modelName) {
        var preset = CodexConfig
                     ? CodexConfig.contextPresetForModel(modelName)
                     : ({})
        if (!preset || !preset.contextWindow) return
        fContextWindow = String(preset.contextWindow)
        fAutoCompactLimit = String(preset.autoCompactLimit)
        fToolOutputLimit = String(preset.toolOutputLimit)
    }

    function selectModel(modelName) {
        fModel = (modelName || "").trim()
        committedModel = fModel
        fReasoningEffort = highestReasoningEffort(fModel)
        useModelContextPreset(fModel)
    }

    function commitTypedModel(modelName) {
        var normalizedModel = (modelName || "").trim()
        if (normalizedModel !== committedModel) selectModel(normalizedModel)
    }

    function useStableContextPreset() {
        var preset = CodexConfig ? CodexConfig.stableContextPreset() : ({})
        if (!preset || !preset.contextWindow) return
        fContextWindow = String(preset.contextWindow)
        fAutoCompactLimit = String(preset.autoCompactLimit)
        fToolOutputLimit = String(preset.toolOutputLimit)
    }

    function clearContext() {
        fContextWindow = ""
        fAutoCompactLimit = ""
        fToolOutputLimit = ""
    }

    function syncFromConfig() {
        fProvider = (CodexConfig && CodexConfig.provider) || "relay"
        fBaseUrl = (CodexConfig && CodexConfig.baseUrl) || ""
        fWireApi = (CodexConfig && CodexConfig.wireApi) || "responses"
        fModel = (CodexConfig && CodexConfig.model) || ""
        committedModel = fModel
        fRequiresAuth = CodexConfig ? CodexConfig.requiresAuth : false
        fReasoningEffort = normalizedReasoningEffort(
            fModel, (CodexConfig && CodexConfig.reasoningEffort) || ""
        )
        fDisableStorage = CodexConfig ? CodexConfig.disableStorage : false
        fContextWindow = (CodexConfig && CodexConfig.modelContextWindow) || ""
        fAutoCompactLimit = (CodexConfig && CodexConfig.modelAutoCompactTokenLimit) || ""
        fToolOutputLimit = (CodexConfig && CodexConfig.toolOutputTokenLimit) || ""
    }

    function applyDraft() {
        if (!CodexConfig) return
        commitTypedModel(fModel)
        CodexConfig.applyConfig({
            "baseUrl": fBaseUrl,
            "provider": fProvider,
            "wireApi": fWireApi,
            "model": fModel,
            "requiresAuth": fRequiresAuth,
            "reasoningEffort": fReasoningEffort,
            "disableStorage": fDisableStorage,
            "modelContextWindow": fContextWindow,
            "modelAutoCompactTokenLimit": fAutoCompactLimit,
            "toolOutputTokenLimit": fToolOutputLimit
        })
    }

    Component.onCompleted: {
        syncFromConfig()
        if (CodexConfig) CodexConfig.refreshReasoningProfiles()
    }

    Connections {
        target: CodexConfig

        function onNotify(level, title, msg) {
            var host = root.Window.window
                       ? root.Window.window.contentItem
                       : root
            var infoBar = Fluent.NotificationManager.infoBar
            var notifyFunction = level === 1 ? infoBar.success
                               : level === 2 ? infoBar.warning
                               : level === 3 ? infoBar.error
                                             : infoBar.info
            notifyFunction(
                host, title, msg, Fluent.Enums.duration.notification,
                Fluent.NotificationManager.posTop
            )
        }

        function onChanged() {
            root.syncFromConfig()
        }

        function onReasoningProfilesChanged() {
            root.fReasoningEffort = root.normalizedReasoningEffort(
                root.fModel, root.fReasoningEffort
            )
        }
    }

    Fluent.ScrollArea {
        id: scrollArea
        objectName: "mainScrollArea"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: actionBar.top

        Column {
            id: pageColumn
            objectName: "pageColumn"
            width: parent ? parent.width : 0
            leftPadding: root.pagePadding
            rightPadding: root.pagePadding
            topPadding: Fluent.Enums.spacing.xl
            bottomPadding: Fluent.Enums.spacing.xl
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            RowLayout {
                width: pageColumn.innerWidth
                spacing: Fluent.Enums.spacing.m

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Fluent.Enums.spacing.xxs

                    Text {
                        text: "Codex"
                        color: Fluent.Enums.textColor.primary
                        font.pixelSize: Fluent.Enums.typography.displayLarge
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "连接、模型与上下文配置"
                        color: Fluent.Enums.textColor.secondary
                        font.pixelSize: Fluent.Enums.typography.body
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: CodexConfig ? CodexConfig.configPath : ""
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideMiddle
                    }
                }

                Fluent.Badge {
                    text: root.hasDraftChanges ? "待应用" : "已同步"
                    level: root.hasDraftChanges
                           ? Fluent.Enums.statusLevel.warning
                           : Fluent.Enums.statusLevel.success
                }
            }

            ConnectionSection {
                id: connectionSection
                objectName: "connectionSection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                baseUrlValue: root.fBaseUrl
                providerValue: root.fProvider
                wireApiValue: root.fWireApi
                hasKey: CodexConfig ? CodexConfig.hasKey : false
                configBusy: root.configBusy
                onBaseUrlEdited: function(value) { root.fBaseUrl = value }
                onProviderEdited: function(value) { root.fProvider = value }
                onWireApiEdited: function(value) { root.fWireApi = value }
                onSaveKeyRequested: function(value) {
                    if (CodexConfig) CodexConfig.setKey(value)
                }
            }

            ModelSection {
                objectName: "modelSection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                modelValue: root.fModel
                reasoningValue: root.fReasoningEffort
                availableModels: CodexConfig ? CodexConfig.availableModels : []
                loading: root.modelsLoading
                onModelTextEdited: function(value) { root.fModel = value }
                onModelCommitted: function(value) { root.commitTypedModel(value) }
                onModelSelected: function(value) { root.selectModel(value) }
                onEffortSelected: function(value) {
                    root.fReasoningEffort = value
                }
                onFetchRequested: {
                    if (CodexConfig) {
                        CodexConfig.fetchModels(
                            root.fBaseUrl, connectionSection.keyDraft
                        )
                    }
                }
            }

            ContextSection {
                objectName: "contextSection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                currentPreset: root.currentContextPreset
                contextWindowValue: root.fContextWindow
                autoCompactValue: root.fAutoCompactLimit
                toolOutputValue: root.fToolOutputLimit
                compactRatio: root.compactRatio
                compactRatioText: root.compactRatioLabel()
                onPresetRequested: root.useStableContextPreset()
                onContextWindowEdited: function(value) {
                    root.fContextWindow = value
                }
                onAutoCompactEdited: function(value) {
                    root.fAutoCompactLimit = value
                }
                onToolOutputEdited: function(value) {
                    root.fToolOutputLimit = value
                }
                onClearRequested: root.clearContext()
            }

            AdvancedSection {
                objectName: "advancedSection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                requiresAuthValue: root.fRequiresAuth
                disableStorageValue: root.fDisableStorage
                onRequiresAuthToggled: function(value) {
                    root.fRequiresAuth = value
                }
                onDisableStorageToggled: function(value) {
                    root.fDisableStorage = value
                }
            }

            Item {
                width: 1
                height: Fluent.Enums.spacing.xl
            }
        }
    }

    Rectangle {
        id: actionBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 72
        color: Fluent.Enums.stateColor.controlBg
        border.width: Fluent.Enums.border.thin
        border.color: Fluent.Enums.stateColor.borderLight
        z: 10

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: root.pagePadding
            anchors.rightMargin: root.pagePadding
            spacing: Fluent.Enums.spacing.m

            Text {
                Layout.fillWidth: true
                text: root.hasDraftChanges
                      ? "有未应用的配置更改"
                      : "当前界面已与 config.toml 同步"
                color: root.hasDraftChanges
                       ? Fluent.Enums.statusLevel.warningColor
                       : Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Fluent.Button {
                style: Fluent.Enums.button.style_default
                text: "重新读取"
                enabled: !root.configBusy
                onClicked: if (CodexConfig) CodexConfig.reload()
            }

            Fluent.Button {
                style: Fluent.Enums.button.style_primary
                text: root.configBusy ? "处理中..." : "应用更改"
                enabled: !root.configBusy
                         && root.hasDraftChanges
                         && root.fBaseUrl.trim().length > 0
                onClicked: root.applyDraft()
            }
        }
    }
}
