import QtQuick
import PrismQML as Fluent

Fluent.Expander {
    id: root

    property bool requiresAuthValue: false
    property bool disableStorageValue: false

    signal requiresAuthToggled(bool value)
    signal disableStorageToggled(bool value)

    title: "兼容性与隐私"
    content: "仅第三方 API 或特殊协议场景需要调整"
    expanded: false

    Column {
        width: parent ? parent.width : 0
        spacing: Fluent.Enums.spacing.l

        Fluent.Toggle {
            id: authToggle
            width: parent.width
            controlType: Fluent.Enums.toggle.control_switch
            type: Fluent.Enums.toggle.type_subtitle
            text: "启用本地路由映射"
            subtitle: "requires_openai_auth · Chat Completions 或非 GPT 模型时使用"
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
            width: parent.width
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
