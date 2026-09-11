// 桌宠悬浮面板本体(明细卡片 / 余额气泡 / 桌宠本体 / 右键菜单)。
// 拆成独立组件的原因:窗口只管生命周期与位置,面板单独可渲染、可核验。
// 布局约定:卡片与气泡水平居中、桌宠固定在右下角;卡片每一行都是固定高度,
// 行高之和 = detailContentHeight,窗口高度由它反推,因此不会出现内容被裁掉。
import QtQuick

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

    // 桌面宠物悬浮窗的统一配色
    property var surfaceColor
    property var panelColor
    property var borderColor
    property var separatorColor
    property var primaryTextColor
    property var secondaryTextColor
    property var mutedTextColor
    property var accentColor
    property var dangerColor
    property var shadowColor

    // 数据(全部来自 NewApiPet 的只读属性,窗口负责取值与降级)
    property var ready
    property var failed
    property var empty
    property var alertState
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
    Item {
        id: detailPanel
        visible: panel.mode === "detail"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: panel.cardTop
        width: panel.panelWidth
        height: panel.cardHeight

        // 柔和投影:同尺寸矩形下移 3px 垫底
        Rectangle {
            anchors.fill: card
            anchors.topMargin: 3
            radius: card.radius
            color: panel.shadowColor
        }

        Rectangle {
            id: card
            objectName: "petCard"
            anchors.fill: parent
            radius: 16
            color: panel.panelColor
            border.color: panel.borderColor
            border.width: 1
            clip: true

            // 行高清单(改动时同步 PetWindow.detailContentHeight):
            // 24 + 1 + 52 + 34 + 14 + 14 + 90 + 14 + 8*7(间距)+ 12*2(内边距)= 321
            Column {
                id: cardColumn
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 12
                anchors.bottomMargin: 12
                spacing: 8

                // ---------------------------------------- 头部:令牌名 + 有效期 + 操作
                Item {
                    id: headerRow
                    width: parent.width
                    height: 24

                    Text {
                        id: titleLabel
                        anchors.left: parent.left
                        anchors.right: actions.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.tokenName
                        font.pixelSize: 14
                        font.bold: true
                        color: panel.primaryTextColor
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignLeft
                        maximumLineCount: 1
                    }

                    Row {
                        id: actions
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, 96)
                            text: panel.expiresText
                            font.pixelSize: 10
                            color: panel.mutedTextColor
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignRight
                        }

                        PetChipButton {
                            emphasized: true
                            label: "刷新"
                            normalTextColor: panel.secondaryTextColor
                            emphasizedTextColor: "#3E5BD8"
                            onActivated: if (panel.petReady) NewApiPet.refresh()
                        }

                        PetChipButton {
                            label: "收起"
                            normalTextColor: panel.secondaryTextColor
                            onActivated: petWindow.toggleDetail()
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: panel.separatorColor
                }

                // ---------------------------------------- 额度与今日用量
                Row {
                    width: parent.width
                    height: 52
                    spacing: 10

                    PetStatCard {
                        width: (parent.width - 10) / 2
                        caption: panel.primaryBalanceCaption
                        value: panel.primaryBalanceText
                        highlight: true
                        danger: panel.failed || panel.empty || panel.primaryNegative
                        surfaceColor: panel.surfaceColor
                        borderColor: panel.borderColor
                        captionColor: panel.mutedTextColor
                        valueColor: panel.primaryTextColor
                        highlightColor: panel.accentColor
                        dangerColor: panel.dangerColor
                    }

                    PetStatCard {
                        width: (parent.width - 10) / 2
                        caption: "今日已用"
                        value: panel.todayAmount
                        surfaceColor: panel.surfaceColor
                        borderColor: panel.borderColor
                        captionColor: panel.mutedTextColor
                        valueColor: panel.primaryTextColor
                        highlightColor: panel.accentColor
                        dangerColor: panel.dangerColor
                    }
                }

                // ---------------------------------------- 另一套口径 + 账户余额新鲜度
                Item {
                    width: parent.width
                    height: 14

                    Text {
                        anchors.left: parent.left
                        anchors.right: accountFresh.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.secondaryBalanceText
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        id: accountFresh
                        anchors.right: parent.right
                        width: Math.min(implicitWidth, parent.width / 2)
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.accountFreshText
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: Text.AlignRight
                    }
                }

                // ---------------------------------------- Token 简写条
                Rectangle {
                    width: parent.width
                    height: 34
                    radius: 10
                    color: panel.surfaceColor
                    border.color: panel.borderColor
                    border.width: 1

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.right: tokenTotal.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "今日 Token"
                            font.pixelSize: 10
                            color: panel.mutedTextColor
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "输入 " + panel.promptTokensText
                            font.pixelSize: 11
                            color: panel.primaryTextColor
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "输出 " + panel.completionTokensText
                            font.pixelSize: 11
                            color: panel.primaryTextColor
                        }
                    }

                    Text {
                        id: tokenTotal
                        anchors.right: tokenCount.left
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.grantedText === "∞" || panel.grantedText === "—"
                              ? panel.grantedText
                              : "总额 " + panel.grantedText
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                    }

                    Text {
                        id: tokenCount
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.todayCountText
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                    }
                }

                // ---------------------------------------- 累计已用 + 数据状态
                Item {
                    width: parent.width
                    height: 14

                    Text {
                        anchors.left: parent.left
                        anchors.right: statusLabel.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: "累计已用 " + panel.usedText
                        font.pixelSize: 10
                        color: panel.secondaryTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        id: statusLabel
                        anchors.right: parent.right
                        width: Math.min(implicitWidth, parent.width / 2)
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.statusText
                        font.pixelSize: 10
                        color: panel.failed ? panel.dangerColor : panel.mutedTextColor
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        horizontalAlignment: Text.AlignRight
                    }
                }

                // ---------------------------------------- 最近调用
                Text {
                    width: parent.width
                    height: 14
                    text: "最近调用"
                    font.pixelSize: 10
                    color: panel.mutedTextColor
                }

                ListView {
                    id: logList
                    width: parent.width
                    // 固定三行高度:不足三行时底部留白,卡片底边与桌宠的间距始终恒定。
                    height: 90
                    clip: true
                    spacing: 3
                    model: panel.logRows

                    delegate: PetLogRow {
                        required property int index
                        required property var modelData

                        width: logList.width
                        timeText: modelData.time
                        modelText: modelData.model
                        tokensText: modelData.tokens
                        costText: modelData.quotaText
                        striped: index % 2 === 1
                    }
                }

                Text {
                    width: parent.width
                    height: 14
                    text: panel.logFooterText
                    font.pixelSize: 10
                    color: panel.mutedTextColor
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignLeft
                    maximumLineCount: 1
                }
            }
        }
    }

    // ============================================================ 余额气泡
    Item {
        id: bubble
        visible: panel.mode === "bubble"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: panel.bubbleTop
        width: panel.panelWidth
        height: panel.bubbleAreaHeight

        Rectangle {
            anchors.fill: bubbleBody
            anchors.topMargin: 3
            radius: bubbleBody.radius
            color: panel.shadowColor
        }

        Rectangle {
            id: bubbleBody
            anchors.fill: parent
            radius: 14
            color: panel.surfaceColor
            border.color: panel.alertState ? "#F0B9B9" : panel.borderColor
            border.width: 1

            // 指向桌宠的小尖角:横向对齐桌宠中心,气泡中心与桌宠不同轴时也不会"指错"
            Rectangle {
                id: bubbleTail
                width: 14
                height: 14
                radius: 3
                rotation: 45
                color: bubbleBody.color
                border.color: bubbleBody.border.color
                border.width: 1
                x: Math.max(14, Math.min(parent.width - 28,
                                         petSprite.x + petSprite.width / 2
                                         - panel.panelWidth / 2 - width / 2))
                anchors.bottom: parent.bottom
                anchors.bottomMargin: -6
            }

            Column {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 9
                spacing: 1

                Text {
                    width: parent.width
                    text: panel.ready
                          ? panel.tokenName + " · " + panel.expiresText
                          : panel.statusText
                    font.pixelSize: 10
                    color: panel.mutedTextColor
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Row {
                    width: parent.width
                    spacing: 8

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.primaryBalanceCaption
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.primaryBalanceText
                        font.pixelSize: 20
                        font.bold: true
                        color: (panel.alertState || panel.primaryNegative)
                               ? panel.dangerColor : panel.accentColor
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: panel.ready ? "Tokens " + panel.promptTokensText
                                            + " / " + panel.completionTokensText : ""
                        font.pixelSize: 10
                        color: panel.mutedTextColor
                    }
                }

                Text {
                    width: parent.width
                    text: panel.todaySummary
                    font.pixelSize: 11
                    color: panel.failed ? panel.dangerColor : panel.secondaryTextColor
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
    }

    // ============================================================ 桌宠本体
    PetSprite {
        id: petSprite
        objectName: "petSprite"
        width: panel.spriteSize
        height: 128
        anchors.right: parent.right
        anchors.rightMargin: panel.spriteRightMargin
        // 贴底定位:三种形态下桌宠屏幕位置恒定,且一定在窗口内
        y: panel.spriteTop
        imagePath: panel.ready && NewApiPet.configPetImage !== ""
                   ? NewApiPet.configPetImage : ""
        alert: panel.alertState
    }

    // 桌宠的拖动 / 点击 / 右键交互层(与明细面板/气泡互不遮挡)
    MouseArea {
        id: petMouse
        x: petSprite.x - 6
        y: petSprite.y - 6
        width: petSprite.width + 12
        height: petSprite.height + 12
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
                contextMenu.openAt()
            } else {
                petWindow.toggleDetail()
            }
        }
        onEntered: petWindow.showBubble()
    }

    // ============================================================ 右键菜单
    // 菜单打开时,点击其他任意位置先关闭菜单
    MouseArea {
        anchors.fill: parent
        visible: contextMenu.visible
        z: 40
        onClicked: contextMenu.visible = false
    }

    Rectangle {
        id: contextMenu
        objectName: "petContextMenu"
        visible: false
        width: 156
        height: menuColumn.height + 12
        radius: 12
        color: panel.surfaceColor
        border.color: panel.borderColor
        border.width: 1
        z: 50

        function openAt() {
            x = Math.max(0, petSprite.x + petSprite.width / 2 - width / 2)
            y = Math.max(0, petSprite.y - height - 4)
            visible = true
        }

        Column {
            id: menuColumn
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 6
            spacing: 2

            Repeater {
                model: [
                    { "label": "立即刷新", "action": "refresh" },
                    { "label": "明细面板", "action": "detail" },
                    { "label": "设置…", "action": "settings" },
                    { "label": "退出桌宠", "action": "quit" }
                ]

                delegate: Rectangle {
                    width: 144
                    height: 30
                    radius: 8
                    color: itemMouse.containsMouse || itemMouse.pressed ? "#EDF2FF" : "transparent"

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        font.pixelSize: 12
                        color: modelData.action === "quit"
                               ? "#C2483F" : panel.primaryTextColor
                    }

                    MouseArea {
                        id: itemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            contextMenu.visible = false
                            if (modelData.action === "refresh" && panel.petReady) {
                                NewApiPet.refresh()
                            } else if (modelData.action === "detail") {
                                petWindow.toggleDetail()
                            } else if (modelData.action === "settings") {
                                if (panel.managerReady) PetManager.openSettings()
                            } else if (modelData.action === "quit") {
                                petWindow.close()
                            }
                        }
                    }
                }
            }
        }
    }
}
