// 应用设置页:沿用 Gitora 的“标题→分组→设置卡片”层级。
import QtQuick
import QtQuick.Window
import PrismQML as Fluent

import "../components"

Item {
    id: root
    objectName: "settingsView"

    readonly property var autoUpdater: Window.window
                                      ? Window.window.autoUpdaterController
                                      : null

    function manualCheck() {
        if (!root.autoUpdater) return
        root.autoUpdater.notifyWhenUpToDate = true
        root.autoUpdater.check()
    }

    PageScaffold {
        id: scaffold
        objectName: "settingsScrollArea"
        anchors.fill: parent
        maxContentWidth: 920

        PageHeader {
            title: "设置"
            subtitle: "外观、语言与应用更新"
            details: "ConfigPilot " + (typeof AppVersion !== "undefined" ? AppVersion : "")
        }

        Fluent.SettingsCardGroup {
            width: scaffold.contentWidth
            title: "个性化"

            Fluent.SettingsCard {
                id: themeCard
                objectName: "themeSettingsCard"

                readonly property var themeValues:
                    ConfigManager ? ConfigManager.themeOptions : []
                readonly property int themeIndex:
                    ConfigManager ? themeValues.indexOf(ConfigManager.theme) : -1

                width: parent ? parent.width : 0
                title: "应用主题"
                content: "跟随系统或固定使用浅色、深色界面"
                icon: Fluent.Enums.icon.dark_theme
                type: Fluent.Enums.settingCard.type_combobox
                model: ["跟随系统", "浅色", "深色"]
                currentIndex: themeIndex >= 0 ? themeIndex : 0
                onIndexSelected: function(index) {
                    if (ConfigManager && index >= 0 && index < themeValues.length)
                        ConfigManager.setTheme(themeValues[index])
                }
            }

            Fluent.SettingsCard {
                id: skinCard
                objectName: "skinSettingsCard"

                readonly property var skinValues:
                    ConfigManager ? ConfigManager.skinOptions : []
                readonly property int skinIndex:
                    ConfigManager ? skinValues.indexOf(ConfigManager.skin) : -1

                width: parent ? parent.width : 0
                title: "应用皮肤"
                content: "切换 ConfigPilot 的视觉风格"
                icon: Fluent.Enums.icon.color
                type: Fluent.Enums.settingCard.type_combobox
                model: ["流畅设计", "新粗野主义", "复古票据", "新拟态"]
                currentIndex: skinIndex >= 0 ? skinIndex : 0
                onIndexSelected: function(index) {
                    if (ConfigManager && index >= 0 && index < skinValues.length)
                        ConfigManager.setSkin(skinValues[index])
                }
            }

            Fluent.SettingsCard {
                objectName: "micaSettingsCard"
                width: parent ? parent.width : 0
                title: "云母效果"
                content: "为窗口应用半透明材质，仅在支持的 Windows 版本生效"
                icon: Fluent.Enums.icon.blur
                type: Fluent.Enums.settingCard.type_switch
                checked: ConfigManager ? ConfigManager.micaEnabled : false
                onSwitchToggled: function(isChecked) {
                    if (ConfigManager) ConfigManager.setMicaEnabled(isChecked)
                }
            }

            Fluent.SettingsCard {
                objectName: "languageSettingsCard"
                width: parent ? parent.width : 0
                title: "界面语言"
                content: "选择 ConfigPilot 的显示语言"
                icon: Fluent.Enums.icon.local_language
                type: Fluent.Enums.settingCard.type_combobox
                model: ["简体中文", "繁體中文", "English", "跟随系统"]
                property var languageValues: ["zh_CN", "zh_TW", "en", "auto"]
                Component.onCompleted: {
                    var index = languageValues.indexOf(Fluent.Translator.language)
                    currentIndex = index >= 0 ? index : 3
                }
                onIndexSelected: function(index) {
                    if (index >= 0 && index < languageValues.length)
                        Fluent.Translator.setLanguage(languageValues[index])
                }
            }
        }

        Fluent.SettingsCardGroup {
            width: scaffold.contentWidth
            title: "应用"

            Fluent.SettingsCard {
                objectName: "updateSettingsCard"
                width: parent ? parent.width : 0
                title: "检查更新"
                content: root.autoUpdater
                        ? "当前版本 " + (typeof AppVersion !== "undefined" ? AppVersion : "")
                        : "更新组件不可用"
                icon: Fluent.Enums.icon.arrow_sync
                type: Fluent.Enums.settingCard.type_push
                buttonText: "检查更新"
                enabled: root.autoUpdater !== null
                onClicked: root.manualCheck()
            }

            Fluent.SettingsCard {
                objectName: "aboutSettingsCard"
                width: parent ? parent.width : 0
                title: "关于 ConfigPilot"
                content: "AI 工具配置与自动化中心 · PrismQML "
                        + (typeof PrismQMLVersion !== "undefined" ? PrismQMLVersion : "")
                icon: Fluent.Enums.icon.info
                type: Fluent.Enums.settingCard.type_push
                buttonText: "查看帮助"
                onClicked: if (Window.window) Window.window.navigateTo("AboutView")
            }
        }
    }
}
