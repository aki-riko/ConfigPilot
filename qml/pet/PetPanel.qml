// 桌宠悬浮面板本体(明细卡片 / 余额气泡 / 桌宠本体 / 右键菜单)。
// 拆成独立组件的原因:窗口只管生命周期与位置,面板单独可渲染、可核验。
// 布局约定:卡片与气泡水平居中、桌宠固定在右下角;卡片每一行都是固定高度,
// 行高之和 = detailContentHeight,窗口高度由它反推,因此不会出现内容被裁掉。
//
// PrismQML 组件清单:
//   卡片 Fluent.Card / 内嵌表面 Fluent.Card(内容条) / 操作按钮 Fluent.Button /
//   分隔线 Fluent.Separator / 明细列表 Fluent.ListView / 气泡表面 Fluent.ShadowedRectangle /
//   右键菜单 Fluent.ContextMenu + Fluent.Action / 文本 Fluent.Label;
//   配色走 Fluent.Enums 主题令牌,字号走 Fluent.Enums.typography。
//
// 三处保留自绘,理由写死在这里,不允许"顺手"换掉:
//   1. 气泡尖角:ShadowedRectangle 画不出指向桌宠的三角(气泡现已改用框架的
//      Fluent.TeachingTip 原生弹层,尖角由框架画;锚点与屏幕夹取仍在这里)。
//   2. 桌宠拖动层:拖动要按 bottomY 坐标系移动窗口,并在松手时
//      NewApiPet.savePosition();Flutter 侧 WindowDragHandle 只发 dragStarted,
//      没有拖动结束信号,换掉会丢"记住位置"行为。
//   3. PetSprite 角色插画:见 PetSprite.qml 文件头。
import QtQuick

import PrismQML as Fluent

Item {
    id: panel
    objectName: "petPanel"

    // 当前形态:pet 只显示桌宠 / bubble 桌宠+余额气泡 / detail 桌宠+明细面板
    property string mode: "bubble"

    // ---------------------------------------------------------------- 布局常量
    // 全部由窗口注入,保证"窗口高度 = 面板高度"永远成立。
    property var panelPadding
    property var panelWidth
    property var petAreaHeight
    property var detailContentHeight
    property var bubbleAreaHeight
    // 气泡弹层高度:气泡现在是独立原生窗口,不再占悬浮窗高度,由窗口按内容给值
    property var bubbleTipHeight
    property var bubbleTop
    property var cardTop
    property var spriteBottomMargin
    property var spriteGap
    property var spriteSize
    property var spriteRightMargin
    // 立绘帧四周的留白比例(与 scripts/generate_pet_art.py 的 --margin 一致):
    // 帽顶离桌宠框顶还有这么多,气泡锚点补上它才落在帽顶而不是脑袋上方。
    readonly property real spriteHeadInset: spriteSize * 0.06

    // 数据(全部来自 NewApiPet 的只读属性,窗口负责取值与降级)
    property var ready
    property var failed
    property var empty
    property var alertState
    // 控制器/管理器是否就绪:面板里"刷新""设置""存位置"都要先过这道判断。
    // 漏注入会让这些入口静默失效(条件恒为假),所以显式声明、由窗口注入。
    property var petReady
    property var managerReady
    property var tokenName
    property var balanceText
    property var todaySummary
    property var todayAmount
    property var todayCountText
    property var promptTokensText
    property var completionTokensText
    property var grantedText
    property var usedText
    property var expiresText
    property var statusText
    property var logRows
    property var logFooterText
    // 余额口径:大数字用 primary*,另一套口径与新鲜度放在对照行里
    property var primaryBalanceText
    property var primaryBalanceCaption
    property var primaryNegative
    property var secondaryBalanceText
    property var accountFreshText

    // ---------------------------------------------------------------- 主题别名
    // 面板统一从 Fluent.Enums 取色;这里只给"语义 → 令牌"一个本地名字,
    // 行内绑定保持和原来一样短。
    readonly property color surfaceColor: Fluent.Enums.surfaceColor
    readonly property color borderColor: Fluent.Enums.borderColor
    readonly property color separatorColor: Fluent.Enums.dividerColor
    readonly property color primaryTextColor: Fluent.Enums.foregroundColor
    readonly property color secondaryTextColor: Fluent.Enums.secondaryForeground
    readonly property color mutedTextColor: Fluent.Enums.tertiaryForeground
    readonly property color accentColor: Fluent.Enums.accentColor
    readonly property color dangerColor: Fluent.Enums.statusLevel.errorColor
    readonly property color shadowColor: Fluent.Enums.shadowColor

    // ---------------------------------------------------------------- 栅格行高
    // Enums 没有"桌宠明细卡行高"这一类令牌,而这几行必须严格相加等于
    // detailContentHeight(352,窗口高度由它反推),所以集中声明在这里,
    // 不允许再散落到各个子元素上去,避免改一处漏一处。
    readonly property int headerRowHeight: 32
    readonly property int statCardHeight: 52
    readonly property int metaRowHeight: 14
    readonly property int tokenBarHeight: 34
    readonly property int logListHeight: 90

    // 明细卡片高度 = 卡片内容高度,窗口高度由它反推。
    readonly property int cardHeight: detailContentHeight

    // 各形态的面板高度:上边距 + 内容 + 空档 + 桌宠 + 下边距
    readonly property int detailPanelHeight: cardTop + cardHeight + spriteGap + spriteSize + spriteBottomMargin
    readonly property int bubblePanelHeight: bubbleTop + bubbleAreaHeight + spriteGap
                                             + spriteSize + spriteBottomMargin
    readonly property int petPanelHeight: petAreaHeight
    // 形态上限高度:窗口尺寸恒定取它,于是窗口永远不做 resize —— 透明无边框窗口
    // 一旦 resize,系统会重建整块渲染表面,用户看到的是整个悬浮窗(含桌宠)
    // 闪 1~2 帧。形态切换改为只改"可见内容 + 窗口遮罩"。
    readonly property int maxPanelHeight: Math.max(detailPanelHeight,
                                                   Math.max(bubblePanelHeight, petPanelHeight))
    readonly property int targetPanelHeight: mode === "detail" ? detailPanelHeight
                                            : (mode === "bubble" ? bubblePanelHeight : petPanelHeight)

    // 高度不做逐帧动画:窗口 resize 是同步系统调用,200ms 内 resize 几十次会把
    // 主线程整个拖住(实测一次 processEvents 被拖到 170ms+,比"瞬变"更糟)。
    // 所以高度一次到位,过渡感全部交给内容层的 opacity + 位移。
    //
    // 收缩必须等淡出跑完:明细卡比气泡高,窗口若立刻缩矮,正在淡出的卡片会被
    // 窗口下沿一路裁掉(看起来像"卡片被抽走")。展开则立即生效 —— 那部分区域
    // 是透明的,先变高不影响观感,还能给上浮动作留出落点。
    //
    // 这里存"滞后的高度值"而不是"滞后的 mode":mode 一旦变化,任何 `= mode`
    // 的绑定都会立刻把高度一起带过去,延后收缩就白写了。0 表示还没锁定,
    // 此时直接用目标高度。
    property int settledPanelHeight: 0
    readonly property int panelHeight: settledPanelHeight > 0 ? settledPanelHeight
                                                              : targetPanelHeight
    onTargetPanelHeightChanged: {
        if (targetPanelHeight >= panelHeight) {
            heightSettleTimer.stop()
            settledPanelHeight = targetPanelHeight
        } else {
            heightSettleTimer.restart()
        }
    }

    // 桌宠永远贴着窗口底边 —— 这样三种形态下桌宠的屏幕位置恒定(窗口只向上长高),
    // 也保证桌宠一定落在窗口内(否则会被裁掉、看不见也点不到)。
    readonly property int spriteTop: panelHeight - spriteBottomMargin - spriteSize

    // 供窗口的信号回调转发:桌宠跳动一下
    function bounce() {
        petSprite.bounce()
    }

    // 面板内的交互(点击气泡/桌宠、右键菜单)统一回调到窗口,由窗口切换形态。
    // 注意:形态与气泡计时器都属于 PetWindow,面板只负责画面。
    function toggleDetail() {
        petWindow.toggleDetail()
    }

    function showBubble() {
        petWindow.showBubble()
    }

    // 收缩时把高度切换延后到淡出结束(见上面 panelHeight 处的说明)。
    Timer {
        id: heightSettleTimer
        interval: Fluent.Enums.duration.medium
        onTriggered: panel.settledPanelHeight = panel.targetPanelHeight
    }

    // ============================================================ 明细面板
    // 位置必须在 childItems()[0]:测试按 childItems()[1] 取气泡。
    Item {
        id: detailPanel
        // 形态切换过渡:淡入淡出 + 从下方轻轻升起,不再瞬变。
        // 用 transform 做位移而不是改 y:本节点是 anchors 定位(topMargin),
        // 同时写 y 会和锚点打架。
        // visible 挂在 opacity 上,淡出结束后才真正隐藏,否则 opacity 动画还没跑
        // 就被 visible=false 掐掉。enabled 必须跟着模式走:opacity=0 的节点照样
        // 吃鼠标事件,不关掉的话气泡形态下会点到隐形的明细卡按钮。
        property real shiftY: panel.mode === "detail" ? 0 : Fluent.Enums.spacing.xl
        Behavior on shiftY {
            NumberAnimation {
                duration: Fluent.Enums.duration.medium
                easing.type: Easing.OutCubic
            }
        }
        transform: Translate { y: detailPanel.shiftY }
        opacity: panel.mode === "detail" ? Fluent.Enums.opacityLevel.visible
                                          : Fluent.Enums.opacityLevel.invisible
        visible: opacity > 0.01
        enabled: panel.mode === "detail"
        Behavior on opacity {
            NumberAnimation {
                duration: Fluent.Enums.duration.medium
                easing.type: Easing.OutCubic
            }
        }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: panel.cardTop
        width: panel.panelWidth
        height: panel.cardHeight

        Fluent.Card {
            id: card
            objectName: "petCard"
            anchors.fill: parent
            // 内边距归零:卡片内部是固定行高栅格,由 cardColumn 自己控制留白。
            // 行高清单(改动时同步 PetWindow.detailContentHeight):
            // 32(头) + 1(分隔) + 52(额度卡) + 14(另一口径对照) + 34(Token 条)
            // + 14(状态行) + 14(最近调用标题) + 90(三行日志) + 14(脚注)
            // + 8*8(行间距) + 12*2(卡片内边距) ≈ 352
            contentPadding: 0
            clip: true

            Column {
                id: cardColumn
                anchors.fill: parent
                anchors.leftMargin: Fluent.Enums.spacing.l
                anchors.rightMargin: Fluent.Enums.spacing.l
                anchors.topMargin: Fluent.Enums.spacing.l
                anchors.bottomMargin: Fluent.Enums.spacing.l
                spacing: Fluent.Enums.spacing.m

                // ---------------------------------------- 头部:令牌名 + 有效期 + 操作
                Item {
                    id: headerRow
                    width: parent.width
                    height: panel.headerRowHeight

                    Fluent.Label {
                        id: titleLabel
                        anchors.left: parent.left
                        anchors.right: actions.left
                        anchors.rightMargin: Fluent.Enums.spacing.m
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.tokenName
                        type: Fluent.Enums.label.type_body_strong
                        font.pixelSize: Fluent.Enums.typography.body
                        customTextColor: panel.primaryTextColor
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignLeft
                        maximumLineCount: 1
                    }

                    Row {
                        id: actions
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Fluent.Enums.spacing.s

                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, panel.panelWidth / 3)
                            text: panel.expiresText
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.micro
                            customTextColor: panel.mutedTextColor
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignRight
                        }

                        Fluent.Button {
                            objectName: "petRefreshButton"
                            style: Fluent.Enums.button.style_primary
                            shape: Fluent.Enums.button.shape_pill
                            text: "刷新"
                            onClicked: if (panel.petReady) NewApiPet.refresh()
                        }

                        Fluent.Button {
                            objectName: "petCollapseButton"
                            style: Fluent.Enums.button.style_default
                            shape: Fluent.Enums.button.shape_pill
                            text: "收起"
                            onClicked: petWindow.toggleDetail()
                        }
                    }
                }

                Fluent.Separator {
                    width: parent.width
                }

                // ---------------------------------------- 额度与今日用量
                Row {
                    width: parent.width
                    height: panel.statCardHeight
                    spacing: Fluent.Enums.spacing.s

                    PetStatCard {
                        width: (parent.width - Fluent.Enums.spacing.s) / 2
                        height: parent.height
                        caption: panel.primaryBalanceCaption
                        value: panel.primaryBalanceText
                        highlight: true
                        danger: panel.failed || panel.empty || panel.primaryNegative
                    }

                    PetStatCard {
                        width: (parent.width - Fluent.Enums.spacing.s) / 2
                        height: parent.height
                        caption: "今日已用"
                        value: panel.todayAmount
                    }
                }

                // ---------------------------------------- 另一套口径 + 账户余额新鲜度
                Item {
                    width: parent.width
                    height: panel.metaRowHeight

                    Fluent.Label {
                        anchors.left: parent.left
                        anchors.right: accountFresh.left
                        anchors.rightMargin: Fluent.Enums.spacing.m
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.secondaryBalanceText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Fluent.Label {
                        id: accountFresh
                        anchors.right: parent.right
                        width: Math.min(implicitWidth, parent.width / 2)
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.accountFreshText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: Text.AlignRight
                    }
                }

                // ---------------------------------------- Token 简写条
                // 内嵌表面用框架的 Fluent.Card(皮肤感知的底色/边框/圆角),
                // 关掉交互避免悬停改色,它只是一条只读数据显示。
                Fluent.Card {
                    objectName: "petTokenBar"
                    width: parent.width
                    height: panel.tokenBarHeight
                    contentPadding: 0
                    interactionEnabled: false
                    border.width: Fluent.Enums.border.thin

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: Fluent.Enums.spacing.m
                        anchors.right: tokenTotal.left
                        anchors.rightMargin: Fluent.Enums.spacing.m
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Fluent.Enums.spacing.l

                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "今日 Token"
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.micro
                            customTextColor: panel.mutedTextColor
                        }
                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "输入 " + panel.promptTokensText
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.captionCompact
                            customTextColor: panel.primaryTextColor
                        }
                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "输出 " + panel.completionTokensText
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.captionCompact
                            customTextColor: panel.primaryTextColor
                        }
                    }

                    Fluent.Label {
                        id: tokenTotal
                        anchors.right: tokenCount.left
                        anchors.rightMargin: Fluent.Enums.spacing.l
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.grantedText === "∞" || panel.grantedText === "—"
                              ? panel.grantedText
                              : "总额 " + panel.grantedText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.mutedTextColor
                    }

                    Fluent.Label {
                        id: tokenCount
                        anchors.right: parent.right
                        anchors.rightMargin: Fluent.Enums.spacing.m
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.todayCountText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.mutedTextColor
                    }
                }

                // ---------------------------------------- 累计已用 + 数据状态
                Item {
                    width: parent.width
                    height: panel.metaRowHeight

                    Fluent.Label {
                        anchors.left: parent.left
                        anchors.right: statusLabel.left
                        anchors.rightMargin: Fluent.Enums.spacing.m
                        anchors.verticalCenter: parent.verticalCenter
                        text: "累计已用 " + panel.usedText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.secondaryTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Fluent.Label {
                        id: statusLabel
                        anchors.right: parent.right
                        width: Math.min(implicitWidth, parent.width / 2)
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.statusText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.failed ? panel.dangerColor : panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: Text.AlignRight
                    }
                }

                // ---------------------------------------- 最近调用
                Fluent.Label {
                    width: parent.width
                    height: panel.metaRowHeight
                    text: "最近调用"
                    type: Fluent.Enums.label.type_caption
                    font.pixelSize: Fluent.Enums.typography.micro
                    customTextColor: panel.mutedTextColor
                }

                // 列表用框架的 Fluent.ListView:它自带视口与滚动条接管,
                // framed 关掉是因为外层 Fluent.Card 已经提供了表面与边框。
                // animated 关掉:这个列表原来是静态三行,不能引入入场动画。
                Fluent.ListView {
                    id: logList
                    objectName: "petLogList"
                    width: parent.width
                    // 固定三行高度:不足三行时底部留白,卡片底边与桌宠的间距始终恒定。
                    height: panel.logListHeight
                    framed: false
                    animated: false
                    spacing: Fluent.Enums.spacing.xxs
                    model: panel.logRows

                    delegate: PetLogRow {
                        required property int index
                        required property var modelData

                        width: parent ? parent.width : 0
                        timeText: modelData.time
                        modelText: modelData.model
                        tokensText: modelData.tokens
                        costText: modelData.quotaText
                        striped: index % 2 === 1
                    }
                }

                Fluent.Label {
                    width: parent.width
                    height: panel.metaRowHeight
                    text: panel.logFooterText
                    type: Fluent.Enums.label.type_caption
                    font.pixelSize: Fluent.Enums.typography.micro
                    customTextColor: panel.mutedTextColor
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignLeft
                    maximumLineCount: 1
                }
            }
        }
    }

    // ============================================================ 余额气泡
    // 位置必须在 childItems()[1]:测试按 childItems()[1] 取气泡锚点。
    // 气泡改用框架的 Fluent.TeachingTip(原生弹层 + 箭头 + 声明式富内容),不再自绘。
    // 它是独立原生窗口,所以本节点退化成"锚点":高度为 0,自身位置决定气泡出现在哪里。
    // 悬停暂停与点击展开由内容里的 MouseArea 接回 —— TipPopup 家族没有悬停钩子;
    // 自动收起仍由 PetWindow 的 hideTimer 管理,因此 duration 用 persistent。
    Item {
        id: bubbleAnchor
        // 气泡是独立原生窗口,不受父级 visible 支配,必须显式开关并跟随形态。
        // 还必须等面板高度切换完成再 show:收缩是延后 200ms 生效的,过渡期间锚点仍在
        // 旧位置,弹层会按旧锚点定格(实测偏 12px),而锚点这次移动来自祖先面板重排、
        // 不是自身几何变化,框架的位置跟踪器看不到,无法自动纠正。
        readonly property bool bubbleShown: panel.mode === "bubble"
                                            && panel.panelHeight === panel.bubblePanelHeight
        onBubbleShownChanged: bubbleShown ? bubbleTip.show() : bubbleTip.close()
        // 初始显示必须延后到事件循环:Component.onCompleted 阶段弹层窗口刚被创建,
        // 此时 show() 会被随后的初始化流程重置回隐藏(实测首帧 visible=False)。
        Component.onCompleted: if (bubbleShown) Qt.callLater(bubbleTip.show)
        // 与明细面板同一套过渡语义(见 detailPanel 处的说明)。
        property real shiftY: panel.mode === "bubble" ? 0 : Fluent.Enums.spacing.l
        Behavior on shiftY {
            NumberAnimation {
                duration: Fluent.Enums.duration.medium
                easing.type: Easing.OutCubic
            }
        }
        transform: Translate { y: bubbleAnchor.shiftY }
        opacity: panel.mode === "bubble" ? Fluent.Enums.opacityLevel.visible
                                         : Fluent.Enums.opacityLevel.invisible
        visible: opacity > 0.01
        enabled: panel.mode === "bubble"
        Behavior on opacity {
            NumberAnimation {
                duration: Fluent.Enums.duration.medium
                easing.type: Easing.OutCubic
            }
        }
        // 框架契约(已在 prismqml 0.4.2.26 wheel 里复核):弹层按 target 的水平中心摆放,
        // 箭头又永远画在弹层的水平中心,且没有屏幕避让 —— 所以"箭头对准脑袋"等价于
        // "target 的中心落在脑袋上",而"弹层不出屏"必须自己夹。
        // 原先锚点钉在窗口正中(桌宠中心 250 vs 窗口中心 162),箭头整整偏左 88px。
        readonly property real headCenterX: petSprite.x + petSprite.width * 0.5
        // 窗口/屏幕几何都在 Qt 侧取(单位一致),QML 里的 screen 对象没有
        // availableGeometry,自己算会直接抛 TypeError。
        readonly property real tipCenterX: {
            // 夹取用弹层真实宽度(尺寸由面板给,所以就是 panelWidth)
            var desired = panel.x + headCenterX
            if (managerReady)
                return PetManager.clampTipCenterX(desired, panel.panelWidth) - panel.x
            return headCenterX
        }
        // 锚点贴桌宠上方留一点间隙:气泡箭头落在帽顶
        // (立绘帧四周有 6% 留白,所以下移 spriteHeadInset 才不是指着脑袋上方)
        x: tipCenterX - width * 0.5
        y: petSprite.y + panel.spriteHeadInset - Fluent.Enums.spacing.xs
        width: panel.panelWidth
        // 锚点保留 1px 高度:零高度 Item 在弹层定位里会被当成零尺寸目标。
        // 它不参与悬浮窗高度计算(bubbleAreaHeight 为 0)。
        height: Math.max(1, panel.bubbleAreaHeight)

        Fluent.TeachingTip {
            id: bubbleTip
            objectName: "petBubbleTip"
            target: bubbleAnchor
            // 气泡在桌宠上方:anchor_bottom 把弹层摆在 target 上方
            anchorPosition: Fluent.Enums.teachingTip.anchor_bottom
            // 尺寸由调用方给:PrismQML 0.4.2.26(本地修复分支)已把 viewWidth/viewHeight
            // 改成公开可配,并把调用方内容挂进 customContentHost,所以富排版气泡成立。
            viewWidth: panel.panelWidth
            viewHeight: panel.bubbleTipHeight
            // 自动收起交给 PetWindow 的 hideTimer(它要支持悬停暂停),
            // 所以这里用 persistent,不让框架自己计时关掉。
            duration: Fluent.Enums.duration.persistent
            closable: false
            modal: false

            // 内容层:三行富排版 + 接回悬停暂停/点击展开的交互层。
            // 弹层窗口自带 padding,这里再给一层对称留白,避免贴边。
            Item {
                width: panel.panelWidth - Fluent.Enums.spacing.xl * 2
                implicitHeight: bubbleColumn.height

                Column {
                    id: bubbleColumn
                    width: parent.width
                    spacing: Fluent.Enums.spacing.micro

                    Fluent.Label {
                        width: parent.width
                        text: panel.ready
                              ? panel.tokenName + " · " + panel.expiresText
                              : panel.statusText
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.micro
                        customTextColor: panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Row {
                        width: parent.width
                        spacing: Fluent.Enums.spacing.m

                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: panel.primaryBalanceCaption
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.micro
                            customTextColor: panel.mutedTextColor
                        }
                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: panel.primaryBalanceText
                            type: Fluent.Enums.label.type_subtitle
                            font.pixelSize: Fluent.Enums.typography.titleLarge
                            customTextColor: (panel.alertState || panel.primaryNegative)
                                             ? panel.dangerColor : panel.accentColor
                        }
                        Fluent.Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: panel.ready ? "Tokens " + panel.promptTokensText
                                                + " / " + panel.completionTokensText : ""
                            type: Fluent.Enums.label.type_caption
                            font.pixelSize: Fluent.Enums.typography.micro
                            customTextColor: panel.mutedTextColor
                        }
                    }

                    Fluent.Label {
                        width: parent.width
                        text: panel.todaySummary
                        type: Fluent.Enums.label.type_caption
                        font.pixelSize: Fluent.Enums.typography.captionCompact
                        customTextColor: panel.failed ? panel.dangerColor
                                                      : panel.secondaryTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }

                // 鼠标停在气泡上时不要自动收起;离开后重新计时;点击展开明细卡。
                // 这里必须调窗口函数:QML 取不到"根对象 id.子元素 id"。
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: petWindow.toggleDetail()
                    onEntered: petWindow.pauseBubbleTimer()
                    onExited: petWindow.resumeBubbleTimer()
                }
            }
        }
    }

    // ============================================================ 桌宠本体
    PetSprite {
        id: petSprite
        objectName: "petSprite"
        width: panel.spriteSize
        height: panel.spriteSize + Fluent.Enums.spacing.m
        anchors.right: parent.right
        anchors.rightMargin: panel.spriteRightMargin
        // 贴底定位:三种形态下桌宠屏幕位置恒定,且一定在窗口内
        y: panel.spriteTop
        // 形象令牌由后端解析(preset:<id> / 绝对路径 / vector / 空=默认内置立绘)。
        // 这里不再挂 panel.ready:立绘跟凭证就绪与否无关,挂上会让桌宠在启动瞬间
        // 先闪一下自绘形体再换成立绘。
        imagePath: NewApiPet && NewApiPet.petImageSource ? NewApiPet.petImageSource : ""
        // 姿势帧表(角色 → 绝对路径);空表 = 只有单图或自绘形体,状态机自动降级
        frames: NewApiPet && NewApiPet.petImageFrames ? NewApiPet.petImageFrames : ({})
        alert: panel.alertState
    }

    // 桌宠的拖动 / 点击 / 右键交互层(与明细面板/气泡互不遮挡)
    // 保留自绘 MouseArea:见文件头"三处保留自绘"第 2 条(拖动要写回位置)。
    MouseArea {
        id: petMouse
        x: petSprite.x - Fluent.Enums.spacing.s
        y: petSprite.y - Fluent.Enums.spacing.s
        width: petSprite.width + Fluent.Enums.spacing.l
        height: petSprite.height + Fluent.Enums.spacing.l
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        cursorShape: Qt.OpenHandCursor
        z: 10

        property real lastX: 0
        property real lastY: 0
        property bool moved: false

        onPressed: function (mouse) {
            lastX = mouse.x
            lastY = mouse.y
            moved = false
            if (mouse.button === Qt.LeftButton) cursorShape = Qt.ClosedHandCursor
            petSprite.poke()
        }
        onPositionChanged: function (mouse) {
            if (!pressed || mouse.buttons !== Qt.LeftButton) return
            var dx = mouse.x - lastX
            var dy = mouse.y - lastY
            if (!moved && Math.abs(dx) < 4 && Math.abs(dy) < 4) return
            moved = true
            petWindow.x += dx
            petWindow.bottomY += dy
            // 拖着走时按横向速度前倾,松手回正(纯观感,不影响落点位置)
            petSprite.lean(dx * 2.5)
        }
        onReleased: function (mouse) {
            cursorShape = Qt.OpenHandCursor
            petSprite.lean(0)
            if (moved && panel.petReady) {
                NewApiPet.savePosition(Math.round(petWindow.x), Math.round(petWindow.bottomY))
            }
        }
        onClicked: function (mouse) {
            if (moved) return
            petSprite.poke()
            if (mouse.button === Qt.RightButton) {
                // 框架菜单:在指针处弹出;屏幕避让/点外关闭由 PopupWindowCore 接管。
                contextMenu.popup(mouse.x, mouse.y, petMouse)
            } else {
                // 点桌宠 = 打招呼,再展开明细
                petSprite.playPose("wave", 900)
                petWindow.toggleDetail()
            }
        }
        onEntered: {
            petSprite.poke()
            petWindow.showBubble()
        }
    }

    // ============================================================ 右键菜单
    // Fluent.ContextMenu(PopupWindowCore 封装):自动处理点外关闭、屏幕避让。
    // autoBindRightClick 关掉 —— 右键由上方 petMouse 统一接管(它还要管拖动)。
    Fluent.ContextMenu {
        id: contextMenu
        objectName: "petContextMenu"
        autoBindRightClick: false

        onActionTriggered: function (actionId) {
            if (actionId === "refresh") {
                if (panel.petReady) NewApiPet.refresh()
            } else if (actionId === "detail") {
                petWindow.toggleDetail()
            } else if (actionId === "settings") {
                if (panel.managerReady) PetManager.openSettings()
            } else if (actionId === "quit") {
                petWindow.close()
            }
        }

        Fluent.Action { actionId: "refresh"; text: "立即刷新"; enabled: panel.petReady }
        Fluent.Action { actionId: "detail"; text: "明细面板" }
        Fluent.Action { actionId: "settings"; text: "设置…" }
        Fluent.Action { actionId: "quit"; text: "退出桌宠" }
    }
}
