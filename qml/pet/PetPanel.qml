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
//   1. 气泡尖角:ShadowedRectangle 画不出指向桌宠的三角,整块气泡仍属悬浮窗
//      共用透明表面,框架的 TipPopup/TeachingTip 是独立原生弹窗 + 纯文本模型,
//      没有悬停暂停/自动收起钩子,塞不进这套固定栅格。
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
    property var bubbleTop
    property var cardTop
    property var spriteBottomMargin
    property var spriteGap
    property var spriteSize
    property var spriteRightMargin

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

    readonly property int panelHeight: {
        // detail:上边距 + 卡片 + 空档 + 桌宠 + 下边距
        if (mode === "detail") return cardTop + cardHeight + spriteGap + spriteSize + spriteBottomMargin
        // bubble:气泡顶边 + 气泡 + 空档 + 桌宠 + 下边距
        if (mode === "bubble") return bubbleTop + bubbleAreaHeight + spriteGap + spriteSize + spriteBottomMargin
        // pet:只放下桌宠
        return petAreaHeight
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

    // ============================================================ 明细面板
    // 位置必须在 childItems()[0]:测试按 childItems()[1] 取气泡。
    Item {
        id: detailPanel
        visible: panel.mode === "detail"
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
    // 位置必须在 childItems()[1]:测试用它定位气泡里的 MouseArea。
    // 表面改用 Fluent.ShadowedRectangle(SDF 阴影,随皮肤给出正确的投影),
    // 尖角仍自绘 —— 见文件头"三处保留自绘"第 1 条。
    Item {
        id: bubble
        visible: panel.mode === "bubble"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: panel.bubbleTop
        width: panel.panelWidth
        height: panel.bubbleAreaHeight

        Fluent.ShadowedRectangle {
            id: bubbleBody
            anchors.fill: parent
            color: panel.surfaceColor
            radius: Fluent.Enums.radius.xlarge
            // 告警态:边框用主题语义红 diluted,仍随主题切换。
            border.color: panel.alertState
                          ? Qt.alpha(Fluent.Enums.statusLevel.errorColor, Fluent.Enums.opacityLevel.medium)
                          : panel.borderColor
            border.width: Fluent.Enums.border.thin
            shadowLevel: Fluent.Enums.shadow.level4

            Column {
                anchors.fill: parent
                anchors.leftMargin: Fluent.Enums.spacing.l
                anchors.rightMargin: Fluent.Enums.spacing.l
                anchors.topMargin: Fluent.Enums.spacing.m
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
                    customTextColor: panel.failed ? panel.dangerColor : panel.secondaryTextColor
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: petWindow.toggleDetail()
                // 鼠标停在气泡上时不要自动收起;离开后重新计时。
                // 这里必须调窗口函数:QML 取不到"根对象 id.子元素 id"(petWindow.hideTimer
                // 恒为 undefined),直接写会抛 "Cannot call method 'stop' of undefined"。
                onEntered: petWindow.pauseBubbleTimer()
                onExited: petWindow.resumeBubbleTimer()
            }
        }

        // 指向桌宠的小尖角:横向对齐桌宠中心,气泡中心与桌宠不同轴时也不会"指错"
        Rectangle {
            id: bubbleTail
            width: Fluent.Enums.spacing.l
            height: Fluent.Enums.spacing.l
            radius: Fluent.Enums.radius.tiny
            rotation: 45
            color: bubbleBody.color
            border.color: bubbleBody.border.color
            border.width: Fluent.Enums.border.thin
            x: Math.max(Fluent.Enums.spacing.l,
                        Math.min(bubble.width - Fluent.Enums.spacing.xxxl,
                                 petSprite.x + petSprite.width / 2
                                 - panel.panelWidth / 2 - width / 2))
            anchors.bottom: bubbleBody.bottom
            anchors.bottomMargin: -Fluent.Enums.spacing.s
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
        imagePath: panel.ready && NewApiPet.configPetImage !== ""
                   ? NewApiPet.configPetImage : ""
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
        }
        onPositionChanged: function (mouse) {
            if (!pressed || mouse.buttons !== Qt.LeftButton) return
            var dx = mouse.x - lastX
            var dy = mouse.y - lastY
            if (!moved && Math.abs(dx) < 4 && Math.abs(dy) < 4) return
            moved = true
            petWindow.x += dx
            petWindow.bottomY += dy
        }
        onReleased: function (mouse) {
            cursorShape = Qt.OpenHandCursor
            if (moved && panel.petReady) {
                NewApiPet.savePosition(Math.round(petWindow.x), Math.round(petWindow.bottomY))
            }
        }
        onClicked: function (mouse) {
            if (moved) return
            if (mouse.button === Qt.RightButton) {
                // 框架菜单:在指针处弹出;屏幕避让/点外关闭由 PopupWindowCore 接管。
                contextMenu.popup(mouse.x, mouse.y, petMouse)
            } else {
                petWindow.toggleDetail()
            }
        }
        onEntered: petWindow.showBubble()
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
