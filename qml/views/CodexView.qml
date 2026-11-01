// Codex 配置页
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import PrismQML as Fluent

Item {
    id: root
    objectName: "codexView"

    // 本页是否处于活动状态：工具箱是本页的一部分，必须跟着本页显隐。
    // 外抽屉是宿主窗口外侧的独立 HWND，切页不会把它带走，不跟随就会在
    // Claude/设置页外面留一个只属于 Codex 的维护工具箱。
    // 从 visible 派生而不是等页面栈写 pageActive：前者由 StackedWidget 的
    // `visible: index === _displayIndex` 直接驱动，0.5/0.7 两代引擎都成立；
    // 后者是 0.7 才有的可选契约（StackedPageActivityController 写入只读属性
    // 会抛错并被静默跳过），拿它当唯一依据会让旧版工具箱永远打不开。
    readonly property bool pageActive: root.visible

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
    readonly property int contentMaxWidth: 1180
    readonly property real contentInset: Math.max(
        pagePadding, (width - contentMaxWidth) / 2
    )
    // 底部操作栏高度依赖此值；缺失会让 actionBar 高度变成 NaN 而整条页脚不可见。
    readonly property int controlHeight: Fluent.Enums.controlSize.buttonHeight
    readonly property int profilesRevision: CodexConfig
                                            ? CodexConfig.profilesRevision
                                            : 0
    // 密钥框里现有内容（可能与后端回显的 key 不同，改动即算草稿）。
    property string keyDraft: ""
    readonly property var currentContextPreset: {
        var revision = profilesRevision
        return CodexConfig ? CodexConfig.stableContextPreset() : ({})
    }
    readonly property var millionContextPreset: {
        var revision = profilesRevision
        return CodexConfig ? CodexConfig.millionContextPreset() : ({})
    }
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
            || keyDraft !== (CodexConfig.authKeyPreview || "").trim()
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
        useContextPreset(preset)
    }

    function useMillionContextPreset() {
        var preset = CodexConfig ? CodexConfig.millionContextPreset() : ({})
        useContextPreset(preset)
    }

    function useContextPreset(preset) {
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

    function sandboxModeSummary() {
        if (!CodexConfig) return "当前未设置 sandbox_mode"
        var value = CodexConfig.sandboxMode || ""
        return value.length > 0
                ? "当前 sandbox_mode = \"" + value + "\""
                : "当前未设置 sandbox_mode（Codex 默认走沙盒执行）"
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
        // 同步时把密钥草稿对齐到后端回显值：否则刚打开页面就显示「待应用」。
        keyDraft = (CodexConfig && CodexConfig.authKeyPreview) || ""
    }

    function applyDraft() {
        if (!CodexConfig) return
        commitTypedModel(fModel)
        // 密钥框回显的是「当前生效的那把 key」，只有真的被改过才随本次应用写入，
        // 否则每次点「应用更改」都会把环境变量认证硬改成 auth.json。
        var preview = (CodexConfig.authKeyPreview || "").trim()
        var draft = connectionSection ? connectionSection.keyDraft.trim() : ""
        var key = draft !== preview ? draft : ""
        root.keyDraft = draft
        var authSource = key.length > 0
                         ? "auth_json"
                         : (fRequiresAuth
                            ? "auth_json"
                            : (CodexConfig.authSource === "environment"
                               ? "environment" : "none"))
        CodexConfig.applyConfig({
            "baseUrl": fBaseUrl,
            "provider": fProvider,
            "wireApi": fWireApi,
            "model": fModel,
            "requiresAuth": fRequiresAuth,
            "authSource": authSource,
            "envKey": CodexConfig.envKey,
            "key": key,
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

    // 维护类操作全部收进外抽屉，避免六个按钮横铺在页面上。
    // pageActive 让抽屉只在本页可见时展开，切到 Claude/设置页会自动收起。
    ToolboxDrawer {
        id: codexToolbox
        pageActive: root.pageActive
        configBusy: root.configBusy
        hasRestorableChanges: CodexConfig ? CodexConfig.hasRestorableChanges : false
        availableModels: CodexConfig ? CodexConfig.availableModels : []
        modelsLoading: root.modelsLoading
        subagentModel: CodexConfig ? CodexConfig.subagentModel : ""
        subagentReasoningEffort: CodexConfig ? CodexConfig.subagentReasoningEffort : ""
        onRepairRelayAuthRequested: {
            var key = connectionSection ? connectionSection.keyDraft.trim() : ""
            if (CodexConfig) CodexConfig.repairRelayAuth(key)
        }
        onSandboxStopgapRequested: sandboxStopgapDialog.open()
        onRestoreInitialRequested: restoreInitialDialog.open()
        onRepairSubagentDefaultsRequested: function(model) {
            if (CodexConfig) CodexConfig.repairSubagentDefaults(model)
        }
        // 抽屉里的「获取模型」与模型页共用同一次请求：key 取密钥框现填的值，
        // 没填则由后端回落到 auth.json / 环境变量里的那把。
        onModelsFetchRequested: {
            if (CodexConfig) {
                CodexConfig.fetchModels(
                    root.fBaseUrl, connectionSection.keyDraft
                )
            }
        }
        onReloadRequested: if (CodexConfig) CodexConfig.reload()
    }

    Fluent.ConfirmDialog {
        id: restoreInitialDialog
        objectName: "restoreInitialDialog"
        level: Fluent.Enums.statusLevel.warning
        title: "恢复初始设置"
        message: "只恢复 ConfigPilot 实际写入且此后未被外部修改的设置。"
                 + "\n\n工作区信任设置（[projects.*]）以及 notify、features "
                 + "等其它 Codex 配置不会改变。API Key 也只会在仍为 "
                 + "ConfigPilot 写入值时恢复。"
        messageAlignment: Text.AlignLeft
        confirmText: "确认恢复"
        cancelText: "取消"
        onConfirmed: {
            if (CodexConfig) CodexConfig.restoreInitialSettings()
        }
    }

    Fluent.ConfirmDialog {
        id: sandboxStopgapDialog
        objectName: "sandboxStopgapDialog"
        level: Fluent.Enums.statusLevel.warning
        title: "沙盒止血（临时）"
        message: "Codex 在 Windows 上会为沙盒执行配置本地沙盒账号，"
                 + "账号首次登录未完成时 Windows 会弹出「无法检查 Windows 设置」。"
                 + "\n\n" + root.sandboxModeSummary() + "，写入后为 "
                 + "\"danger-full-access\"。"
                 + "\n\n只写这一项：其余配置与 [windows]、[projects.*] 等段落原样保留。"
                 + "\n代价是 Codex 不再使用沙盒隔离；该写入可用「恢复初始设置」还原。"
        messageAlignment: Text.AlignLeft
        confirmText: "确认写入"
        cancelText: "取消"
        onConfirmed: {
            if (CodexConfig) CodexConfig.applySandboxStopgap()
        }
    }

    Fluent.ScrollArea {
        id: scrollArea
        objectName: "mainScrollArea"
        padding: Fluent.Enums.spacing.none
        orientation: Qt.Vertical
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: actionBar.top

        Item {
            id: pageFrame
            width: Math.min(
                parent ? parent.width : 0, root.contentMaxWidth
            )
            x: Math.max(
                0, ((parent ? parent.width : 0) - width) / 2
            )
            implicitHeight: pageColumn.implicitHeight
            height: pageColumn.implicitHeight

            Column {
                id: pageColumn
                objectName: "pageColumn"
                width: pageFrame.width
                leftPadding: root.pagePadding
                rightPadding: root.pagePadding
                topPadding: Fluent.Enums.spacing.l
                bottomPadding: Fluent.Enums.spacing.l
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
                        font.pixelSize: Fluent.Enums.typography.display
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "连接、模型与上下文配置"
                        color: Fluent.Enums.textColor.secondary
                        font.pixelSize: Fluent.Enums.typography.bodySmall
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
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

            Rectangle {
                width: pageColumn.innerWidth
                height: Fluent.Enums.border.thin
                color: Fluent.Enums.stateColor.borderLight
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
                hasChatgptAuth: CodexConfig ? CodexConfig.hasChatgptAuth : false
                authSource: CodexConfig ? CodexConfig.authSource : "none"
                envKey: CodexConfig ? CodexConfig.envKey : ""
                envKeyPresent: CodexConfig ? CodexConfig.envKeyPresent : false
                authReady: CodexConfig ? CodexConfig.authReady : true
                keyValue: CodexConfig ? CodexConfig.authKeyPreview : ""
                configBusy: root.configBusy
                onBaseUrlEdited: function(value) { root.fBaseUrl = value }
                onProviderEdited: function(value) { root.fProvider = value }
                onWireApiEdited: function(value) {
                    // 下拉框回传的是协议显示名，写进草稿的必须是 wire_api 标识，
                    // 映射只有一份，在后端 backend/wire_api.py 里。
                    root.fWireApi = CodexConfig
                                    ? CodexConfig.wireApiValueFor(value)
                                    : value
                }
                onImportAuthJsonRequested: function(value) {
                    if (CodexConfig) CodexConfig.importAuthJson(value)
                }
                onRepairRelayAuthRequested: function(value) {
                    if (CodexConfig) CodexConfig.repairRelayAuth(value)
                }
                onSandboxStopgapRequested: sandboxStopgapDialog.open()
                onKeyEdited: function(value) { root.keyDraft = value }
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
                millionPreset: root.millionContextPreset
                contextWindowValue: root.fContextWindow
                autoCompactValue: root.fAutoCompactLimit
                toolOutputValue: root.fToolOutputLimit
                compactRatio: root.compactRatio
                compactRatioText: root.compactRatioLabel()
                onPresetRequested: root.useStableContextPreset()
                onMillionPresetRequested: root.useMillionContextPreset()
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
    }

    Rectangle {
        id: actionBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.controlHeight + 2 * Fluent.Enums.spacing.l
        color: Fluent.Enums.stateColor.controlBg
        border.width: Fluent.Enums.border.thin
        border.color: Fluent.Enums.stateColor.borderLight
        z: 10

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: root.contentInset
            anchors.rightMargin: root.contentInset
            spacing: Fluent.Enums.spacing.m

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
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
                objectName: "codexToolboxButton"
                Layout.minimumWidth: 112
                Layout.preferredWidth: 112
                Layout.maximumWidth: 112
                style: Fluent.Enums.button.style_default
                icon: Fluent.Enums.icon.wrench
                // 工具箱启动即展开，这里只提供手动收起/再打开。
                text: codexToolbox.opened ? "收起工具箱" : "工具箱"
                enabled: !root.configBusy
                onClicked: codexToolbox.opened ? codexToolbox.close()
                                               : codexToolbox.open()
            }

            Fluent.Button {
                Layout.minimumWidth: 128
                Layout.preferredWidth: 128
                Layout.maximumWidth: 128
                style: Fluent.Enums.button.style_primary
                icon: Fluent.Enums.icon.save
                text: root.configBusy ? "处理中..." : "应用更改"
                enabled: !root.configBusy
                         && root.hasDraftChanges
                         && root.fBaseUrl.trim().length > 0
                onClicked: root.applyDraft()
            }
        }
    }
}
