import QtQuick
import PrismQML as Fluent
import "../i18n/ConfigPilotI18n.js" as AppI18n

Column {
    id: root

    property string modelName: ""
    property string reasoningEffort: ""
    signal effortSelected(string value)

    width: parent ? parent.width : 0
    spacing: Fluent.Enums.spacing.s

    function highestOptionText() {
        for (var i = effortBox.effortOptions.length - 1; i >= 0; i--) {
            if (effortBox.effortOptions[i].value) return effortBox.effortOptions[i].text
        }
        return "未设置"
    }

    function reloadEffortOptions() {
        var sourceOptions = CodexConfig
                            ? CodexConfig.reasoningOptionsForModel(root.modelName)
                            : []
        var displayOptions = []
        for (var i = 0; i < sourceOptions.length; i++) {
            var option = sourceOptions[i]
            displayOptions.push({
                "value": option.value,
                "text": option.value === "max"
                        ? AppI18n.tr("reasoning_max", activeLanguage())
                        : option.text
            })
        }
        effortBox.effortOptions = displayOptions
        effortBox.syncCurrentIndex()
    }

    function activeLanguage() {
        return Fluent.Translator.language === "auto"
               ? Fluent.Translator.detectSystemLanguage()
               : Fluent.Translator.language
    }

    onModelNameChanged: reloadEffortOptions()

    Text {
        text: "思考等级"
        color: Fluent.Enums.textColor.secondary
        font.pixelSize: Fluent.Enums.typography.body
        font.bold: true
        font.family: Fluent.Enums.fontFamily
    }

    Fluent.ComboBoxDefault {
        id: effortBox
        width: Math.min(280, root.width)
        property var effortOptions: []
        model: effortOptions

        function syncCurrentIndex() {
            var found = 0
            for (var i = 0; i < effortOptions.length; i++) {
                if (effortOptions[i].value === root.reasoningEffort) found = i
            }
            if (currentIndex !== found) currentIndex = found
        }

        Component.onCompleted: Qt.callLater(root.reloadEffortOptions)
        onEffortOptionsChanged: syncCurrentIndex()
        onActivated: function(index) {
            if (index >= 0 && index < effortOptions.length) {
                root.effortSelected(effortOptions[index].value || "")
            }
        }

        Connections {
            target: root
            function onReasoningEffortChanged() {
                effortBox.syncCurrentIndex()
            }
        }

        Connections {
            target: CodexConfig
            function onReasoningProfilesChanged() {
                root.reloadEffortOptions()
            }
        }

        Connections {
            target: Fluent.Translator
            function onLanguageUpdated() {
                root.reloadEffortOptions()
            }
        }
    }

    Text {
        width: root.width
        text: "选择新模型时默认使用最高可用档：" + root.highestOptionText()
        color: Fluent.Enums.textColor.tertiary
        font.pixelSize: Fluent.Enums.typography.caption
        font.family: Fluent.Enums.fontFamily
        wrapMode: Text.WordWrap
    }
}
