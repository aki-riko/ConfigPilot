import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent
import "../i18n/ConfigPilotI18n.js" as AppI18n

// 「思考等级」也走统一的 FormField：标题 → 说明 → 控件，与其它字段同一套
// 行序。之前这里自己写了一套标题/控件/说明，且下拉宽度写死封顶 280px，
// 宽窗口右侧留出一大片空白，和其它字段对不齐。
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

    FormField {
        width: parent.width
        label: "思考等级"
        hint: "选择新模型时默认使用最高可用档：" + root.highestOptionText()

        Fluent.ComboBoxDefault {
            id: effortBox
            objectName: "effortBox"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
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
    }
}
