import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property string baseUrlValue: ""
    property string providerValue: ""
    property string wireApiValue: ""
    property bool hasKey: false
    property bool hasChatgptAuth: false
    property string authSource: "none"
    property string envKey: ""
    property bool envKeyPresent: false
    property bool authReady: true
    property bool configBusy: false
    // 当前生效的 API key 明文（后端 authKeyPreview），直接回显在输入框里，
    // 不再用「已设置/未设置」把真实值藏起来。
    property string keyValue: ""
    readonly property string keyDraft: keyInput.text

    signal baseUrlEdited(string value)
    signal providerEdited(string value)
    signal wireApiEdited(string value)
    signal importAuthJsonRequested(string value)
    signal repairRelayAuthRequested(string value)
    signal sandboxStopgapRequested()
    signal keyEdited(string value)

    // 让页面能把密钥框内容复位成刚应用过的值（应用后草稿与后端一致）。
    function setKeyText(value) {
        keyInput.text = value
    }

    // 失焦/回车只做规范化，不写盘：密钥统一由「应用更改」随草稿一起提交。
    function commitKey() {
        keyInput.text = keyInput.text.trim()
    }

    // 失焦/回车即把地址补成实际会写入 config.toml 的形式（末尾缺 /v1 时补 /v1）。
    // 规范化交给后端 CodexConfig.normalizedBaseUrl，避免界面和写入各算一套。
    function commitBaseUrl() {
        var draft = baseUrlEdit.text.trim()
        var normalized = typeof CodexConfig === "undefined"
                         ? draft : CodexConfig.normalizedBaseUrl(draft)
        if (normalized !== baseUrlEdit.text) {
            // 改 text 会经 onTextChanged 把补全后的地址回传给草稿，不再重复发一次
            baseUrlEdit.text = normalized
            return
        }
        if (normalized.length > 0 && normalized !== root.baseUrlValue) {
            root.baseUrlEdited(normalized)
        }
    }

    function commitAuthJson() {
        var value = authJsonInput.text.trim()
        if (value.length === 0) return
        root.importAuthJsonRequested(value)
        authJsonInput.text = ""
    }

    title: "连接与认证"
    content: ""
    icon: Fluent.Enums.icon.server
    expanded: true
    contentPadding: 0

    headerContent: Component {
        Fluent.Badge {
            text: root.authSource === "environment"
                  ? (root.envKeyPresent ? "环境变量已设置" : "环境变量未设置")
                  : root.hasChatgptAuth ? "ChatGPT 已登录"
                  : root.hasKey ? "API 密钥已设置" : "未设置认证"
            level: root.authSource !== "none" && root.authReady
                   ? Fluent.Enums.statusLevel.success
                   : Fluent.Enums.statusLevel.warning
        }
    }

    // 内容高度必须用 implicitHeight：Column 的 implicitHeight 已含上下 padding，
    // 而 childrenRect.height 不含。此前用 childrenRect 导致卡片底部被裁。
    Item {
        width: parent ? parent.width : 0
        implicitHeight: cardColumn.implicitHeight
        height: implicitHeight

        Column {
            id: cardColumn
            objectName: "connectionCardColumn"
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            // ---------- 地址与协议 ----------
            FormField {
                width: cardColumn.innerWidth
                label: "API 地址"
                keyName: "base_url"
                hint: "未包含 /v1 时自动补全（失焦或回车即回填）"

                Fluent.LineEdit {
                    id: baseUrlEdit
                    objectName: "baseUrlEdit"
                    Layout.fillWidth: true
                    placeholderText: "https://api.example.com/v1"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.baseUrlValue
                    })
                    onTextChanged: {
                        if (text !== root.baseUrlValue) root.baseUrlEdited(text)
                    }
                    onEditingFinished: root.commitBaseUrl()
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
                uniformCellWidths: columns === 2
                columnSpacing: Fluent.Enums.spacing.l
                rowSpacing: Fluent.Enums.spacing.l
                readonly property real equalItemWidth: columns === 2
                                                       ? Math.max(
                                                             0,
                                                             (width - columnSpacing) / 2
                                                         )
                                                       : width

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: connectionGrid.equalItemWidth
                    Layout.maximumWidth: connectionGrid.equalItemWidth
                    label: "提供商标识"
                    keyName: "provider"

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

                FormField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: connectionGrid.equalItemWidth
                    Layout.maximumWidth: connectionGrid.equalItemWidth
                    label: "通信协议"
                    keyName: "wire_api"

                    Fluent.ComboBoxDefault {
                        id: wireApiBox
                        objectName: "wireApiComboBox"
                        Layout.fillWidth: true
                        property var protocolOptions: []

                        // 候选与显示名都来自后端 CodexConfig.wireApiOptions()：
                        // 界面只出现协议名，写入 config.toml 的 wire_api 标识由后端
                        // 映射（backend/wire_api.py）。配置里若留着认不出的历史值，
                        // 后端原样透传，这里也照原样多列一项，避免被静默改写。
                        function reloadOptions() {
                            var source = CodexConfig
                                         ? CodexConfig.wireApiOptions() : []
                            var options = []
                            for (var i = 0; i < source.length; i++) {
                                options.push({
                                    "value": source[i].value,
                                    "text": source[i].text
                                })
                            }
                            var current = root.wireApiValue
                            var known = false
                            for (var j = 0; j < options.length; j++) {
                                if (options[j].value === current) known = true
                            }
                            if (!known && current.length > 0) {
                                options.push({
                                    "value": current,
                                    "text": CodexConfig
                                            ? CodexConfig.wireApiLabel(current)
                                            : current
                                })
                            }
                            protocolOptions = options
                            wireApiBox.syncCurrentIndex()
                        }

                        function syncCurrentIndex() {
                            var found = 0
                            for (var i = 0; i < protocolOptions.length; i++) {
                                if (protocolOptions[i].value === root.wireApiValue) {
                                    found = i
                                }
                            }
                            if (currentIndex !== found) currentIndex = found
                        }

                        model: protocolOptions
                        Component.onCompleted: Qt.callLater(reloadOptions)
                        onActivated: function(index) {
                            if (index >= 0 && index < protocolOptions.length) {
                                // 回传显示名，由 CodexView 交给后端映射成标识
                                root.wireApiEdited(protocolOptions[index].text)
                            }
                        }
                        Connections {
                            target: root
                            function onWireApiValueChanged() {
                                wireApiBox.reloadOptions()
                            }
                        }
                    }
                }
            }

            Fluent.Separator {
                width: cardColumn.innerWidth
            }

            // ---------- 凭据 ----------
            FormField {
                width: cardColumn.innerWidth
                label: "API 密钥"
                hint: root.authSource === "environment"
                      ? (root.envKeyPresent
                         ? "当前使用环境变量 " + (root.envKey || "未指定")
                         : "环境变量 " + (root.envKey || "未指定")
                           + " 当前没有值；填入密钥后随「应用更改」写入")
                      : "修改后随「应用更改」一起写入"

                // 遮罩与眼睛切换全部交给 PrismQML 的 LineEdit：
                // type_password 会内置眼睛按钮并自动切换 showPassword，
                // 不需要在外部再叠一个显隐按钮（那样会出现两个眼睛）。
                Fluent.LineEdit {
                    id: keyInput
                    objectName: "codexApiKeyEdit"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    inputType: Fluent.Enums.input.type_password
                    enabled: !root.configBusy
                    placeholderText: "粘贴 API key"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.keyValue
                    })
                    onAccepted: root.commitKey()
                    onEditingFinished: root.commitKey()
                    onTextChanged: root.keyEdited(text)
                    Connections {
                        target: root
                        function onKeyValueChanged() {
                            // 只在用户没在编辑时回填，避免把正在输入的草稿冲掉。
                            if (!keyInput.activeFocus
                                    && keyInput.text !== root.keyValue) {
                                keyInput.text = root.keyValue
                            }
                        }
                    }
                }
            }

            // ---------- 维护操作：说明在左、按钮统一宽度并右对齐 ----------
            RowLayout {
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.m

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignVCenter
                    text: "使用当前输入的密钥修复中转站认证"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    elide: Text.ElideRight
                }

                Fluent.Button {
                    objectName: "repairRelayAuthButton"
                    Layout.minimumWidth: 156
                    Layout.preferredWidth: 156
                    Layout.maximumWidth: 156
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.wrench
                    text: root.configBusy
                          ? "处理中..."
                          : "修复中转站 401"
                    enabled: !root.configBusy
                    onClicked: root.repairRelayAuthRequested(keyInput.text.trim())
                }
            }

            RowLayout {
                width: cardColumn.innerWidth
                spacing: Fluent.Enums.spacing.m

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignVCenter
                    text: "Codex 反复弹出「无法检查 Windows 设置」时写入非沙盒档止血"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    elide: Text.ElideRight
                }

                Fluent.Button {
                    objectName: "sandboxStopgapButton"
                    Layout.minimumWidth: 156
                    Layout.preferredWidth: 156
                    Layout.maximumWidth: 156
                    style: Fluent.Enums.button.style_default
                    icon: Fluent.Enums.icon.wrench
                    text: root.configBusy ? "处理中..." : "沙盒止血（临时）"
                    enabled: !root.configBusy
                    onClicked: root.sandboxStopgapRequested()
                }
            }

            Fluent.Separator {
                width: cardColumn.innerWidth
            }

            FormField {
                width: cardColumn.innerWidth
                label: "ChatGPT JSON 导入"
                hint: "粘贴 Codex auth.json 或 codex2api 兼容 JSON；"
                      + "仅有 refresh_token 时自动换取完整凭据。"

                Fluent.TextEdit {
                    id: authJsonInput
                    objectName: "authJsonInput"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 132
                    enabled: !root.configBusy
                    placeholderText: "{\n  \"refresh_token\": \"...\"\n}"
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0

                    Item {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        implicitHeight: 1
                    }

                    Fluent.Button {
                        objectName: "authJsonImportButton"
                        Layout.minimumWidth: 180
                        Layout.preferredWidth: 180
                        Layout.maximumWidth: 180
                        style: Fluent.Enums.button.style_default
                        icon: Fluent.Enums.icon.arrow_import
                        text: root.configBusy ? "导入中..." : "导入并登录 ChatGPT"
                        enabled: !root.configBusy
                                 && authJsonInput.text.trim().length > 0
                        onClicked: root.commitAuthJson()
                    }
                }
            }
        }
    }
}
