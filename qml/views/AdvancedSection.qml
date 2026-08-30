import QtQuick
import PrismQML as Fluent

Fluent.Card {
    id: root

    property bool requiresAuthValue: false
    property bool disableStorageValue: false

    signal requiresAuthToggled(bool value)
    signal disableStorageToggled(bool value)

    autoHeight: true

    Column {
        width: parent ? parent.width : 0
        spacing: Fluent.Enums.spacing.l

        Column {
            width: parent.width
            spacing: Fluent.Enums.spacing.xxs

            Text {
                text: "兼容性与隐私"
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.subtitle
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }

            Text {
                width: parent.width
                text: "第三方 API 的认证映射与响应存储行为"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
        }

        Fluent.Separator {
            width: parent.width
        }

        Fluent.Toggle {
            id: authToggle

            width: parent.width
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
