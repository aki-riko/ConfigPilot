import QtQuick
import PrismQML as Fluent

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
        property var effortOptions: CodexConfig
                                    ? CodexConfig.reasoningOptionsForModel(root.modelName)
                                    : []
        model: effortOptions

        function syncCurrentIndex() {
            var found = 0
            for (var i = 0; i < effortOptions.length; i++) {
                if (effortOptions[i].value === root.reasoningEffort) found = i
            }
            if (currentIndex !== found) currentIndex = found
        }

        Component.onCompleted: Qt.callLater(syncCurrentIndex)
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
