import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property string modelsJsonValue: "[]"
    property string modelDiscoveryStateValue: "auto"
    property string modelPrefer1mContextStateValue: "auto"
    property string headersValue: ""
    property int headerCount: 0
    property bool clearHeadersValue: false
    property var modelEntries: []

    signal modelsJsonEdited(string value)
    signal modelDiscoveryStateSelected(string value)
    signal modelPrefer1mContextStateSelected(string value)
    signal headersEdited(string value)
    signal clearHeadersToggled(bool value)

    title: "模型与请求头"
    content: "模型发现、模型展示、1M 上下文和额外请求头"
    expanded: false

    readonly property var stateOptions: [
        { "text": "自动", "value": "auto" },
        { "text": "开启", "value": "enabled" },
        { "text": "关闭", "value": "disabled" }
    ]
    readonly property var tierOptions: [
        { "text": "不设置", "value": "" },
        { "text": "haiku", "value": "haiku" },
        { "text": "sonnet", "value": "sonnet" },
        { "text": "opus", "value": "opus" },
        { "text": "fable", "value": "fable" },
        { "text": "mythos", "value": "mythos" }
    ]

    function syncModels() {
        var parsed = []
        try {
            var value = JSON.parse(root.modelsJsonValue || "[]")
            if (Array.isArray(value)) parsed = value
        } catch (error) {
            parsed = []
        }
        root.modelEntries = parsed.map(function(item) {
            return typeof item === "string" ? { "name": item } : item
        })
    }

    function emitModels(next) {
        root.modelEntries = next
        root.modelsJsonEdited(JSON.stringify(next))
    }

    function updateModel(index, patch) {
        if (index < 0 || index >= root.modelEntries.length) return
        var next = root.modelEntries.slice()
        var item = Object.assign({}, next[index], patch)
        if (patch.hasOwnProperty("name")) {
            item.name = String(patch.name || "").trim()
        }
        if (patch.hasOwnProperty("labelOverride")) {
            var label = String(patch.labelOverride || "").trim()
            if (label) item.labelOverride = label
            else delete item.labelOverride
        }
        if (patch.hasOwnProperty("supports1m") && !patch.supports1m) {
            delete item.prefer1m
        }
        if (patch.hasOwnProperty("anthropicFamilyTier")
                && !patch.anthropicFamilyTier) {
            delete item.anthropicFamilyTier
            delete item.isFamilyDefault
        }
        next[index] = item
        emitModels(next)
    }

    function addModel() {
        var next = root.modelEntries.slice()
        next.push({ "name": "" })
        emitModels(next)
    }

    function removeModel(index) {
        var next = root.modelEntries.slice()
        next.splice(index, 1)
        emitModels(next)
    }

    function stateIndex(options, value) {
        for (var i = 0; i < options.length; i++) {
            if (options[i].value === value) return i
        }
        return 0
    }

    function tierIndex(value) {
        return stateIndex(root.tierOptions, value || "")
    }

    Component.onCompleted: syncModels()
    onModelsJsonValueChanged: syncModels()

    Column {
        id: contentColumn
        width: parent ? parent.width : 0
        spacing: Fluent.Enums.spacing.l

        GridLayout {
            id: behaviorGrid
            width: parent.width
            columns: width < 620 ? 1 : 2
            uniformCellWidths: columns === 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.s

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "模型发现"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "启动时从网关的 /v1/models 自动读取模型"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
                Fluent.ComboBoxDefault {
                    id: discoveryBox
                    Layout.fillWidth: true
                    model: root.stateOptions
                    Component.onCompleted: currentIndex = root.stateIndex(
                        root.stateOptions, root.modelDiscoveryStateValue
                    )
                    onActivated: function(index) {
                        if (index >= 0 && index < root.stateOptions.length) {
                            root.modelDiscoveryStateSelected(
                                root.stateOptions[index].value
                            )
                        }
                    }
                    Connections {
                        target: root
                        function onModelDiscoveryStateValueChanged() {
                            discoveryBox.currentIndex = root.stateIndex(
                                root.stateOptions,
                                root.modelDiscoveryStateValue
                            )
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "默认 1M 上下文"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "优先选择第一个模型的 1M 变体"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
                Fluent.ComboBoxDefault {
                    id: prefer1mBox
                    Layout.fillWidth: true
                    model: root.stateOptions
                    Component.onCompleted: currentIndex = root.stateIndex(
                        root.stateOptions, root.modelPrefer1mContextStateValue
                    )
                    onActivated: function(index) {
                        if (index >= 0 && index < root.stateOptions.length) {
                            root.modelPrefer1mContextStateSelected(
                                root.stateOptions[index].value
                            )
                        }
                    }
                    Connections {
                        target: root
                        function onModelPrefer1mContextStateValueChanged() {
                            prefer1mBox.currentIndex = root.stateIndex(
                                root.stateOptions,
                                root.modelPrefer1mContextStateValue
                            )
                        }
                    }
                }
            }
        }

        RowLayout {
            width: parent.width
            Text {
                Layout.fillWidth: true
                text: "模型列表"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.caption
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Fluent.Button {
                objectName: "claudeAddModelButton"
                Layout.minimumWidth: 112
                Layout.preferredWidth: 112
                Layout.maximumWidth: 112
                style: Fluent.Enums.button.style_default
                icon: Fluent.Enums.icon.add
                text: "添加模型"
                onClicked: root.addModel()
            }
        }

        Text {
            width: parent.width
            visible: root.modelEntries.length === 0
            text: "未配置固定模型；模型发现开启时将使用网关返回的列表"
            color: Fluent.Enums.textColor.tertiary
            font.pixelSize: Fluent.Enums.typography.caption
            font.family: Fluent.Enums.fontFamily
            wrapMode: Text.WordWrap
        }

        Column {
            id: modelColumn
            width: parent.width
            spacing: Fluent.Enums.spacing.s

            Repeater {
                id: modelRepeater
                model: root.modelEntries

                delegate: ClaudeModelEntry {
                    width: modelColumn.width
                    entry: modelData
                    indexValue: index
                    tierOptions: root.tierOptions
                    onPatchRequested: function(patch) {
                        root.updateModel(indexValue, patch)
                    }
                    onRemoveRequested: root.removeModel(indexValue)
                }
            }
        }

        GridLayout {
            id: headersGrid
            width: parent.width
            columns: width < 680 ? 1 : 2
            uniformCellWidths: columns === 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.l

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: headersGrid.columns === 2
                                       ? (headersGrid.width - headersGrid.columnSpacing) / 2
                                       : headersGrid.width
                Layout.maximumWidth: headersGrid.columns === 2
                                     ? (headersGrid.width - headersGrid.columnSpacing) / 2
                                     : headersGrid.width
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    Layout.fillWidth: true
                    text: root.headerCount > 0
                          ? "额外请求头 · 已保存 " + root.headerCount + " 项"
                          : "额外请求头 · 可选"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Fluent.Enums.controlSize.checkboxOuter
                    spacing: Fluent.Enums.spacing.s

                    Text {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        text: "输入 JSON 对象覆盖现有值；敏感内容不会回显"
                        color: Fluent.Enums.textColor.tertiary
                        font.pixelSize: Fluent.Enums.typography.caption
                        font.family: Fluent.Enums.fontFamily
                        elide: Text.ElideRight
                    }

                    Fluent.Toggle {
                        id: clearHeadersToggle
                        objectName: "claudeClearHeadersToggle"
                        Layout.alignment: Qt.AlignVCenter
                        enabled: root.headerCount > 0
                        visible: root.headerCount > 0
                        controlType: Fluent.Enums.toggle.control_checkbox
                        type: Fluent.Enums.toggle.type_default
                        text: "应用时删除"
                        Component.onCompleted: Qt.callLater(function() {
                            checked = root.clearHeadersValue
                        })
                        onToggled: function(checkedValue) {
                            root.clearHeadersToggled(checkedValue)
                        }
                        Connections {
                            target: root
                            function onClearHeadersValueChanged() {
                                if (clearHeadersToggle.checked !== root.clearHeadersValue) {
                                    clearHeadersToggle.checked = root.clearHeadersValue
                                }
                            }
                        }
                    }
                }
                Fluent.TextEdit {
                    id: headersEdit
                    objectName: "claudeHeadersEdit"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 108
                    enabled: !root.clearHeadersValue
                    placeholderText: "{\n  \"X-Tenant\": \"tenant-id\"\n}"
                    Component.onCompleted: Qt.callLater(function() {
                        text = root.headersValue
                    })
                    onTextEdited: {
                        if (text !== root.headersValue) root.headersEdited(text)
                    }
                    Connections {
                        target: root
                        function onHeadersValueChanged() {
                            if (headersEdit.text !== root.headersValue) {
                                headersEdit.text = root.headersValue
                            }
                        }
                    }
                }
            }
        }
    }
}
