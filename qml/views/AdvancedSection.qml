import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property bool requiresAuthValue: false
    property bool disableStorageValue: false

    signal requiresAuthToggled(bool value)
    signal disableStorageToggled(bool value)

    title: "兼容性与隐私"
    content: ""
    icon: Fluent.Enums.icon.shield
    expanded: false
    contentPadding: 0

    headerContent: Component {
        Fluent.Badge {
            text: root.requiresAuthValue || root.disableStorageValue ? "已调整" : "默认"
            level: root.requiresAuthValue || root.disableStorageValue
                   ? Fluent.Enums.statusLevel.info
                   : Fluent.Enums.statusLevel.neutral
        }
    }

    // 高度用 implicitHeight（含 padding）；childrenRect 不含 padding 会裁掉底部。
    Item {
        width: parent ? parent.width : 0
        implicitHeight: contentColumn.implicitHeight
        height: implicitHeight

        Column {
            id: contentColumn
            width: parent ? parent.width : 0
            leftPadding: Fluent.Enums.spacing.l
            rightPadding: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.l
            spacing: Fluent.Enums.spacing.l

            readonly property real innerWidth: Math.max(
                0, width - leftPadding - rightPadding
            )

            Fluent.Toggle {
                id: authToggle
                objectName: "requiresAuthToggle"
                width: contentColumn.innerWidth
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_subtitle
                text: "启用本地路由映射"
                subtitle: "requires_openai_auth · 使用 auth.json 的 OpenAI 认证"
                Component.onCompleted: Qt.callLater(function() {
                    checked = root.requiresAuthValue
                })
                onToggled: function(checkedValue) {
                    root.requiresAuthToggled(checkedValue)
                }
                Connections {
                    target: root
                    function onRequiresAuthValueChanged() {
                        if (authToggle.checked !== root.requiresAuthValue) {
                            authToggle.checked = root.requiresAuthValue
                        }
                    }
                }
            }

            Fluent.Toggle {
                id: storageToggle
                objectName: "disableStorageToggle"
                width: contentColumn.innerWidth
                controlType: Fluent.Enums.toggle.control_switch
                type: Fluent.Enums.toggle.type_subtitle
                text: "禁用响应存储"
                subtitle: "disable_response_storage · 部分第三方中转要求开启"
                Component.onCompleted: Qt.callLater(function() {
                    checked = root.disableStorageValue
                })
                onToggled: function(checkedValue) {
                    root.disableStorageToggled(checkedValue)
                }
                Connections {
                    target: root
                    function onDisableStorageValueChanged() {
                        if (storageToggle.checked !== root.disableStorageValue) {
                            storageToggle.checked = root.disableStorageValue
                        }
                    }
                }
            }
        }
    }
}
