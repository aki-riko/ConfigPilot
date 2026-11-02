import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

// 工具箱：把维护类操作收进一个内抽屉（mode_inside，在 Codex 页面内部滑出），
// 不再让六个按钮横铺在设置页里。抽屉内容全是"低频、有副作用"的操作，
// 因此每项都带一句说明，避免误点。
//
// 用内抽屉而不是外抽屉：外抽屉是贴着宿主窗口外侧的独立 HWND，切页不会带着它走，
// 必须额外写一套「页面失活就收起」的补丁；而内抽屉天然跟随本页，遮罩也只盖住
// 本页范围，不会压暗整窗。
Fluent.Drawer {
    id: root

    objectName: "codexToolboxDrawer"
    // 内抽屉：在页面内部滑出，遮罩只覆盖本页。
    mode: Fluent.Enums.drawer.mode_inside
    position: Fluent.Enums.position.right
    drawerWidth: 360
    // 内抽屉的横向模式高度跟随父级（整页高），drawerHeight 不参与布局。
    drawerHeight: 420
    animationDuration: Fluent.Enums.duration.medium
    // 覆盖宿主即本页容器：抽屉挂在本页里、遮罩也只盖本页。
    // 必须显式传入而不是依赖 parent —— Drawer 打开时会把自身重挂到覆盖宿主，
    // parent 会变，靠它取宿主会拿到重挂之后的自己。
    // PrismQML 0.7.1.15 起 Drawer 才真正尊重 overlayTarget（此前硬编码窗口内容项）。
    property Item overlayHost: null
    overlayTarget: overlayHost

    property bool configBusy: false
    property bool hasRestorableChanges: false
    // 「修复降智」改为手动选择模型：可选项只来自「获取模型」的真实结果，
    // 不再由代码内置任何兜底模型（旧实现写死 gpt-6-sol，会把用户在 Codex
    // 侧自己调好的子代理配置覆盖掉）。
    property var availableModels: []
    property bool modelsLoading: false
    property string subagentModel: ""
    property string subagentReasoningEffort: ""
    // 下拉框当前选中的模型；空值表示还没选，此时「执行」保持禁用。
    property string selectedSubagentModel: ""
    // 默认关闭：启动时只显示「工具箱」按钮，不自动弹出。
    // 抽屉内容全是低频、有副作用的维护操作，不该一进页面就挡在配置内容前面。
    //
    // 所属页面是否处于活动状态。工具箱是本页的一部分，切到 Claude / 设置页时
    // 本页整体隐藏，抽屉随之不可见；这里仍保留显式收起，避免内抽屉在页面
    // 重新可见时残留展开态或遮罩。默认 true 保持单独实例化（测试/预览）时
    // 不依赖宿主页面的行为。
    property bool pageActive: true

    signal repairRelayAuthRequested()
    signal sandboxStopgapRequested()
    signal restoreInitialRequested()
    signal repairSubagentDefaultsRequested(string model)
    signal modelsFetchRequested()
    signal reloadRequested()

    // 回显「当前 config.toml 里已经是什么」，让用户在覆盖前看得见差别。
    function subagentSummary() {
        if (!root.subagentModel) {
            return "当前未设置子代理默认模型"
        }
        return "当前 " + root.subagentModel
                + " / " + (root.subagentReasoningEffort || "默认档")
    }

    function subagentModelIndex() {
        var list = root.availableModels || []
        if (!root.selectedSubagentModel) return -1
        for (var i = 0; i < list.length; i++) {
            if (list[i] === root.selectedSubagentModel) return i
        }
        return -1
    }

    // 列表刷新后校正选中项：已选的仍在表里就保持，否则回到未选状态。
    function syncSelection() {
        var list = root.availableModels || []
        if (root.selectedSubagentModel
                && list.indexOf(root.selectedSubagentModel) < 0) {
            root.selectedSubagentModel = ""
        }
    }

    // 还没手动选过时，把下拉预选到 config.toml 里已有的模型，让用户一眼
    // 看出「现在是什么」。必须在完成时和属性变化时都调用一次：页面若在配置
    // 读完之后才创建，subagentModel 一上来就有值，等不到变化通知。
    function preselectCurrentModel() {
        if (root.selectedSubagentModel || !root.subagentModel) return
        var list = root.availableModels || []
        if (list.indexOf(root.subagentModel) >= 0) {
            root.selectedSubagentModel = root.subagentModel
        }
    }

    // 页面失活（切到 Claude / 设置页）：收起抽屉。
    // 内抽屉虽然会随本页隐藏，但仍显式收起，避免回到本页时残留遮罩。
    function closeForInactivePage() {
        if (!root.opened) return
        root.close()
    }

    onPageActiveChanged: {
        if (!root.pageActive) closeForInactivePage()
    }

    Component.onCompleted: Qt.callLater(preselectCurrentModel)

    // 可用模型列表变化后校正选中项（例如重新获取列表、或切换中转站），
    // 并在还没选过时按当前配置预选一次。
    onAvailableModelsChanged: {
        syncSelection()
        preselectCurrentModel()
    }
    onSubagentModelChanged: preselectCurrentModel()

    // 注意：Drawer 的 contentItem 已经 anchors.fill + margins(spacing.xl)，
    // 内容必须填满它（anchors.fill），不能再自己按 drawerWidth 定宽——那样会
    // 多算一份边距，把右侧的「执行」按钮挤出面板边界。
    ColumnLayout {
        id: contentColumn
        anchors.fill: parent
        spacing: Fluent.Enums.spacing.m

            Text {
                Layout.fillWidth: true
                text: "维护工具箱"
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.bodyLarge
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }

            Text {
                Layout.fillWidth: true
                text: "这些操作会直接改动 Codex 配置，请确认后再执行。"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }

            Fluent.Separator {
                Layout.fillWidth: true
            }

            ToolRow {
                Layout.fillWidth: true
                title: "修复中转站 401"
                description: "用当前填写的密钥重写中转站认证来源"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                onTriggered: root.repairRelayAuthRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "沙盒止血（临时）"
                description: "反复弹出「无法检查 Windows 设置」时写入非沙盒档"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                onTriggered: root.sandboxStopgapRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "修复降智"
                description: "写入你选中的模型，推理强度取该模型最高档"
                icon: Fluent.Enums.icon.wrench
                busy: root.configBusy
                enabled: root.selectedSubagentModel.length > 0
                onTriggered: root.repairSubagentDefaultsRequested(
                                 root.selectedSubagentModel)
            }

            SubagentPicker {
                Layout.fillWidth: true
            }

            ToolRow {
                Layout.fillWidth: true
                title: "恢复初始设置"
                description: root.hasRestorableChanges
                             ? "还原 ConfigPilot 写入且此后未被外部修改的设置"
                             : "当前没有可恢复的修改记录"
                icon: Fluent.Enums.icon.arrow_reset
                busy: root.configBusy
                enabled: !root.configBusy && root.hasRestorableChanges
                onTriggered: root.restoreInitialRequested()
            }

            ToolRow {
                Layout.fillWidth: true
                title: "重新读取"
                description: "丢弃界面草稿，按磁盘上的 config.toml 重新载入"
                icon: Fluent.Enums.icon.arrow_sync
                busy: root.configBusy
                onTriggered: root.reloadRequested()
            }

            Item { Layout.fillHeight: true }
    }

    // 抽屉内单条操作：左侧标题+说明，右侧按钮。整体可点，也保留独立按钮语义。
    component ToolRow: RowLayout {
        id: toolRow
        property string title: ""
        property string description: ""
        property string icon: ""
        property bool busy: false
        signal triggered()

        spacing: Fluent.Enums.spacing.m

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Fluent.Enums.spacing.xxs

            Text {
                Layout.fillWidth: true
                text: toolRow.title
                color: Fluent.Enums.textColor.primary
                font.pixelSize: Fluent.Enums.typography.body
                font.family: Fluent.Enums.fontFamily
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: toolRow.description
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
        }

        Fluent.Button {
            Layout.minimumWidth: 88
            Layout.preferredWidth: 88
            Layout.maximumWidth: 88
            style: Fluent.Enums.button.style_default
            icon: toolRow.icon
            text: toolRow.busy ? "处理中..." : "执行"
            enabled: toolRow.enabled && !toolRow.busy
            onClicked: toolRow.triggered()
        }
    }

    // 「修复降智」的模型选择器：下拉选项只来自「获取模型」的结果。
    // 没有列表时下拉置灰并提示先获取，避免用户以为可以凭手输蒙一个模型名。
    component SubagentPicker: ColumnLayout {
        id: picker

        spacing: Fluent.Enums.spacing.xs

        RowLayout {
            Layout.fillWidth: true
            spacing: Fluent.Enums.spacing.s

            Fluent.ComboBoxDefault {
                id: modelBox
                objectName: "subagentModelBox"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: root.availableModels
                placeholderText: root.availableModels.length > 0
                                 ? "选择模型"
                                 : "先获取模型"
                currentIndex: root.subagentModelIndex()
                enabled: root.availableModels.length > 0 && !root.configBusy

                onActivated: function(index) {
                    var list = root.availableModels || []
                    if (index >= 0 && index < list.length) {
                        root.selectedSubagentModel = list[index]
                    }
                }

                Connections {
                    target: root
                    function onSelectedSubagentModelChanged() {
                        var index = root.subagentModelIndex()
                        if (modelBox.currentIndex !== index) {
                            modelBox.currentIndex = index
                        }
                    }
                }
            }

            Fluent.Button {
                objectName: "subagentModelFetchButton"
                Layout.minimumWidth: 88
                Layout.preferredWidth: 88
                Layout.maximumWidth: 88
                style: Fluent.Enums.button.style_default
                icon: Fluent.Enums.icon.arrow_sync
                text: root.modelsLoading ? "获取中..." : "获取模型"
                enabled: !root.modelsLoading && !root.configBusy
                onClicked: root.modelsFetchRequested()
            }
        }

        Text {
            objectName: "subagentCurrentText"
            Layout.fillWidth: true
            text: root.subagentSummary()
            color: Fluent.Enums.textColor.tertiary
            font.pixelSize: Fluent.Enums.typography.caption
            font.family: Fluent.Enums.fontFamily
            wrapMode: Text.WordWrap
        }
    }
}
