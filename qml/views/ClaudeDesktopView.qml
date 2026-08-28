// Claude Desktop 第三方推理配置页
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import PrismQML as Fluent

Item {
    id: root
    objectName: "claudeDesktopView"

    property string fEndpoint: ""
    property string fAuthScheme: "bearer"
    property string fModels: ""
    property string fApiKey: ""
    property string fHeaders: ""
    property bool fClearApiKey: false
    property bool fClearHeaders: false

    readonly property int pagePadding: width < 720
                                       ? Fluent.Enums.spacing.l
                                       : Fluent.Enums.spacing.xl
    readonly property bool needsActivation: ClaudeDesktopConfig
                                                 && ClaudeDesktopConfig.configPilotProfileExists
                                                 && (!ClaudeDesktopConfig.developerModeEnabled
                                                      || !ClaudeDesktopConfig.thirdPartyEnabled)
    readonly property bool configPilotProfileExists: ClaudeDesktopConfig
                                                    ? ClaudeDesktopConfig.configPilotProfileExists
                                                    : false
    readonly property bool configBusy: ClaudeDesktopConfig
                                               ? ClaudeDesktopConfig.operationBusy
                                               : false
    readonly property int controlHeight: Fluent.Enums.controlSize.buttonHeight
    readonly property bool hasDraftChanges: {
        if (!ClaudeDesktopConfig) return false
        return (root.configPilotProfileExists && needsActivation)
            || (!root.configPilotProfileExists && fEndpoint.trim().length > 0)
            || fEndpoint !== (ClaudeDesktopConfig.endpoint || "")
            || fAuthScheme !== (ClaudeDesktopConfig.authScheme || "bearer")
            || fModels !== (ClaudeDesktopConfig.modelsText || "")
            || fApiKey.trim().length > 0
            || fHeaders.trim().length > 0
            || fClearApiKey
            || fClearHeaders
    }

    function syncFromConfig() {
        fEndpoint = (ClaudeDesktopConfig && ClaudeDesktopConfig.endpoint) || ""
        fAuthScheme = (ClaudeDesktopConfig && ClaudeDesktopConfig.authScheme) || "bearer"
        fModels = (ClaudeDesktopConfig && ClaudeDesktopConfig.modelsText) || ""
        fApiKey = ""
        fHeaders = ""
        fClearApiKey = false
        fClearHeaders = false
    }

    function applyDraft() {
        if (!ClaudeDesktopConfig) return
        ClaudeDesktopConfig.applyConfig({
            "endpoint": fEndpoint,
            "authScheme": fAuthScheme,
            "modelsText": fModels,
            "apiKey": fApiKey,
            "headersText": fHeaders,
            "clearApiKey": fClearApiKey,
            "clearHeaders": fClearHeaders
        })
    }

    Component.onCompleted: syncFromConfig()

    Connections {
        target: ClaudeDesktopConfig

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
    }

    Fluent.ScrollArea {
        id: scrollArea
        objectName: "claudeScrollArea"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: actionBar.top

        Column {
            id: pageColumn
            width: parent ? parent.width : 0
            leftPadding: root.pagePadding
            rightPadding: root.pagePadding
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.m

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
                        text: "Claude Desktop"
                        color: Fluent.Enums.textColor.primary
                        font.pixelSize: Fluent.Enums.typography.displayLarge
                        font.bold: true
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "开发者模式与第三方推理网关"
                        color: Fluent.Enums.textColor.secondary
                        font.pixelSize: Fluent.Enums.typography.body
                        font.family: Fluent.Enums.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }

                Fluent.Badge {
                    text: !root.configPilotProfileExists
                          ? "待创建"
                          : (root.needsActivation ? "待配置" : "已就绪")
                    level: !root.configPilotProfileExists || root.needsActivation
                           ? Fluent.Enums.statusLevel.attention
                           : Fluent.Enums.statusLevel.success
                }
            }

            ClaudeStatusSection {
                objectName: "claudeStatusSection"
                width: pageColumn.innerWidth
                installed: ClaudeDesktopConfig ? ClaudeDesktopConfig.installed : false
                developerModeEnabled: ClaudeDesktopConfig
                                      ? ClaudeDesktopConfig.developerModeEnabled
                                      : false
                thirdPartyEnabled: ClaudeDesktopConfig
                                   ? ClaudeDesktopConfig.thirdPartyEnabled
                                   : false
                configBusy: root.configBusy
                installBusy: ClaudeDesktopConfig ? ClaudeDesktopConfig.installBusy : false
                installCancelable: ClaudeDesktopConfig
                                   ? ClaudeDesktopConfig.installCancelable
                                   : false
                installProgress: ClaudeDesktopConfig
                                 ? ClaudeDesktopConfig.installProgress
                                 : -1
                installStatus: ClaudeDesktopConfig ? ClaudeDesktopConfig.installStatus : ""
                gatewayCanEnable: root.fEndpoint.trim().length > 0
                                  && profileName.length > 0
                profileName: ClaudeDesktopConfig ? ClaudeDesktopConfig.profileName : ""
                configPath: ClaudeDesktopConfig ? ClaudeDesktopConfig.configPath : ""
                configPilotProfileExists: ClaudeDesktopConfig
                                           ? ClaudeDesktopConfig.configPilotProfileExists
                                           : false
                activeProfileName: ClaudeDesktopConfig
                                  ? ClaudeDesktopConfig.activeProfileName
                                  : ""
                canImportActiveProfile: ClaudeDesktopConfig
                                        ? ClaudeDesktopConfig.canImportActiveProfile
                                        : false
                onDeveloperModeToggled: function(value) {
                    if (ClaudeDesktopConfig) {
                        ClaudeDesktopConfig.setDeveloperModeEnabled(value)
                    }
                }
                onGatewayToggled: function(value) {
                    if (ClaudeDesktopConfig) {
                        ClaudeDesktopConfig.setThirdPartyEnabled(value)
                    }
                }
                onInstallRequested: function(product) {
                    if (ClaudeDesktopConfig) {
                        ClaudeDesktopConfig.installProduct(product)
                    }
                }
                onCancelInstallRequested: if (ClaudeDesktopConfig) {
                    ClaudeDesktopConfig.cancelInstall()
                }
                onCloneActiveProfileRequested: if (ClaudeDesktopConfig) {
                    ClaudeDesktopConfig.cloneActiveProfileToConfigPilot()
                }
            }

            ClaudeGatewaySection {
                objectName: "claudeGatewaySection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                endpointValue: root.fEndpoint
                authSchemeValue: root.fAuthScheme
                apiKeyValue: root.fApiKey
                hasApiKey: ClaudeDesktopConfig ? ClaudeDesktopConfig.hasApiKey : false
                clearApiKeyValue: root.fClearApiKey
                onEndpointEdited: function(value) { root.fEndpoint = value }
                onAuthSchemeSelected: function(value) { root.fAuthScheme = value }
                onApiKeyEdited: function(value) { root.fApiKey = value }
                onClearApiKeyToggled: function(value) { root.fClearApiKey = value }
            }

            ClaudeAdvancedSection {
                objectName: "claudeAdvancedSection"
                width: pageColumn.innerWidth
                enabled: !root.configBusy
                modelsValue: root.fModels
                headersValue: root.fHeaders
                headerCount: ClaudeDesktopConfig ? ClaudeDesktopConfig.headerCount : 0
                clearHeadersValue: root.fClearHeaders
                onModelsEdited: function(value) { root.fModels = value }
                onHeadersEdited: function(value) { root.fHeaders = value }
                onClearHeadersToggled: function(value) { root.fClearHeaders = value }
            }

            Item {
                width: 1
                height: Fluent.Enums.spacing.s
            }
        }
    }

    Rectangle {
        id: actionBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.controlHeight + 2 * Fluent.Enums.spacing.m
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
                Layout.alignment: Qt.AlignVCenter
                text: !root.configPilotProfileExists
                      ? (ClaudeDesktopConfig.activeProfileName.length > 0
                         ? "已读取 " + ClaudeDesktopConfig.activeProfileName
                           + " · 应用将新建 ConfigPilot"
                         : (root.hasDraftChanges
                            ? "将新建 ConfigPilot · 应用后请完全退出并重新打开 Claude Desktop"
                            : "尚未创建 ConfigPilot 档案"))
                      : (root.hasDraftChanges
                         ? "有未应用的更改 · 应用后请完全退出并重新打开 Claude Desktop"
                         : "Claude Desktop 配置已同步")
                color: root.hasDraftChanges && root.configPilotProfileExists
                       ? Fluent.Enums.statusLevel.warningColor
                       : Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.bodySmall
                font.bold: root.hasDraftChanges && root.configPilotProfileExists
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Fluent.Button {
                objectName: "claudeOpenDirectoryButton"
                Layout.preferredHeight: root.controlHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_default
                text: "打开目录"
                visible: root.width >= 820
                enabled: !root.configBusy
                onClicked: if (ClaudeDesktopConfig) {
                    ClaudeDesktopConfig.openConfigDirectory()
                }
            }

            Fluent.Button {
                objectName: "claudeReloadButton"
                Layout.preferredHeight: root.controlHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_default
                text: "重新读取"
                enabled: !root.configBusy
                onClicked: if (ClaudeDesktopConfig) ClaudeDesktopConfig.reload()
            }

            Fluent.Button {
                objectName: "claudeApplyButton"
                Layout.preferredHeight: root.controlHeight
                Layout.alignment: Qt.AlignVCenter
                style: Fluent.Enums.button.style_primary
                text: root.configBusy
                      ? "处理中..."
                      : (root.needsActivation
                         ? "启用并应用"
                         : (!root.configPilotProfileExists
                            ? "创建并应用 ConfigPilot"
                            : "应用更改"))
                enabled: !root.configBusy
                         && root.hasDraftChanges
                         && root.fEndpoint.trim().length > 0
                onClicked: root.applyDraft()
            }
        }
    }
}
