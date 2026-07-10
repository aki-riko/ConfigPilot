import QtQuick
import PrismQML as Fluent

Row {
    id: root

    property string modelName: ""
    property string reasoningEffort: ""
    signal effortSelected(string value)

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

        Component.onCompleted: syncCurrentIndex()
        onEffortOptionsChanged: syncCurrentIndex()
        onActivated: function(index) {
            root.effortSelected(effortOptions[index].value || "")
        }

        Connections {
            target: root
            function onReasoningEffortChanged() {
                effortBox.syncCurrentIndex()
            }
        }
    }
}
