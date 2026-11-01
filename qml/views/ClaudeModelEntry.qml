import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Rectangle {
    id: root

    property var entry: ({})
    property int indexValue: 0
    property var tierOptions: []

    signal patchRequested(var patch)
    signal removeRequested()

    width: parent ? parent.width : 0
    color: Fluent.Enums.stateColor.controlBg
    border.width: Fluent.Enums.border.thin
    border.color: Fluent.Enums.stateColor.borderLight
    radius: 4
    implicitHeight: modelCardColumn.implicitHeight
                      + 2 * Fluent.Enums.spacing.m

    function tierIndex(value) {
        for (var i = 0; i < root.tierOptions.length; i++) {
            if (root.tierOptions[i].value === (value || "")) return i
        }
        return 0
    }

    ColumnLayout {
        id: modelCardColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Fluent.Enums.spacing.m
        spacing: Fluent.Enums.spacing.s

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.m

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: "模型 " + (root.indexValue + 1)
                      + (root.entry.labelOverride
                         ? " · " + root.entry.labelOverride
                         : "")
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }
            Fluent.Button {
                objectName: "claudeRemoveModelButton" + root.indexValue
                Layout.minimumWidth: 92
                Layout.preferredWidth: 92
                Layout.maximumWidth: 92
                style: Fluent.Enums.button.style_default
                icon: Fluent.Enums.icon.icon_delete
                text: "移除"
                onClicked: root.removeRequested()
            }
        }

        // 字段单列纵向堆叠、占满整行；并排两列时带说明的字段会比兄弟高一截。
        ColumnLayout {
            id: modelFieldGrid
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Fluent.Enums.spacing.s

            FormField {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                label: "Model ID"

                Fluent.LineEdit {
                    id: modelIdEdit
                    Layout.fillWidth: true
                    text: root.entry.name || ""
                    placeholderText: "claude-sonnet-5"
                    onEditingFinished: root.patchRequested({ "name": text })
                    onAccepted: root.patchRequested({ "name": text })
                }
            }

            FormField {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                label: "Display name"

                Fluent.LineEdit {
                    id: labelEdit
                    Layout.fillWidth: true
                    text: root.entry.labelOverride || ""
                    placeholderText: "留空自动格式化"
                    onEditingFinished: root.patchRequested({ "labelOverride": text })
                    onAccepted: root.patchRequested({ "labelOverride": text })
                }
            }

            Fluent.Toggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_subtitle
                text: "Offer 1M-context variant"
                subtitle: "为此模型提供 1M 上下文变体"
                Component.onCompleted: checked = !!root.entry.supports1m
                onToggled: function(checkedValue) {
                    root.patchRequested({ "supports1m": checkedValue })
                }
            }

            Fluent.Toggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                visible: !!root.entry.supports1m
                enabled: !!root.entry.supports1m
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_subtitle
                text: "Default to 1M context"
                subtitle: "将 1M 变体作为默认选择"
                Component.onCompleted: checked = !!root.entry.prefer1m
                onToggled: function(checkedValue) {
                    root.patchRequested({ "prefer1m": checkedValue })
                }
            }

            FormField {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                label: "Tier alias"

                Fluent.ComboBoxDefault {
                    id: tierBox
                    Layout.fillWidth: true
                    model: root.tierOptions
                    Component.onCompleted: currentIndex = root.tierIndex(
                        root.entry.anthropicFamilyTier
                    )
                    onActivated: function(selectedIndex) {
                        if (selectedIndex >= 0
                                && selectedIndex < root.tierOptions.length) {
                            root.patchRequested({
                                "anthropicFamilyTier": root.tierOptions[selectedIndex].value
                            })
                        }
                    }
                }
            }

            Fluent.Toggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                visible: !!root.entry.anthropicFamilyTier
                enabled: !!root.entry.anthropicFamilyTier
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_subtitle
                text: "Default for tier"
                subtitle: "多个模型共享 Tier 时作为默认"
                Component.onCompleted: checked = !!root.entry.isFamilyDefault
                onToggled: function(checkedValue) {
                    root.patchRequested({ "isFamilyDefault": checkedValue })
                }
            }
        }
    }
}
