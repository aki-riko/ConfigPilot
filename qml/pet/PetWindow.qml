// ConfigPilot 余额桌宠:无边框置顶悬浮窗,气泡显示余额与今日用量。
// 数据由 Python 端 NewApiPet 轮询 new-api 只读接口提供。
import QtQuick
import QtQuick.Window

Window {
    id: petWindow

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    width: 340
    height: petWindow.panelHeight
    // 底边固定在 bottomY,气泡/明细向上展开。声明式绑定让 height→y 在同一
    // 求值周期内原子更新,避免命令式改 y 读到旧 height 造成的跳动。
    y: bottomY >= 0 ? bottomY - height : 0
    title: "ConfigPilot 余额桌宠"
    visible: false

    readonly property bool standalone: typeof PetStandalone !== "undefined" ? PetStandalone : false
    readonly property bool petReady: typeof NewApiPet !== "undefined" && NewApiPet !== null
    readonly property bool managerReady: typeof PetManager !== "undefined" && PetManager !== null

    // 面板高度随模式变化,底边保持不动(气泡向上展开)。
    //  pet:    只显示桌宠
    //  bubble: 桌宠 + 余额气泡
    //  detail: 桌宠 + 明细卡片
    property string mode: "bubble"
    readonly property int petAreaHeight: 148
    readonly property int bubbleAreaHeight: 84
    readonly property int detailAreaHeight: 336
    readonly property int panelHeight: {
        if (mode === "detail") return petAreaHeight + detailAreaHeight
        if (mode === "bubble") return petAreaHeight + bubbleAreaHeight
        return petAreaHeight
    }

    property int bottomY: -1
    property string lastBalance: ""
    property string lastToday: ""

    onClosing: {
        if (standalone) {
            Qt.quit()
        } else if (managerReady) {
            PetManager.petWindowClosed()
        }
    }

    function clampX(value) {
        var maxX = Screen.desktopAvailableWidth - width
        if (maxX < 0) return 0
        return Math.max(0, Math.min(value, maxX))
    }

    Component.onCompleted: {
        var startX = petReady ? NewApiPet.windowX : -1
        var startBottom = petReady ? NewApiPet.windowBottomY : -1
        if (startX === undefined || startX < 0) startX = Screen.desktopAvailableWidth - width - 16
        if (startBottom === undefined || startBottom < 0) startBottom = Screen.desktopAvailableHeight - 12
        x = clampX(startX)
        bottomY = startBottom
        showBubble()
    }

    function showBubble() {
        if (mode === "detail") return
        mode = "bubble"
        hideTimer.restart()
    }

    function hideBubble() {
        if (mode === "bubble") mode = "pet"
    }

    function toggleDetail() {
        if (mode === "detail") {
            mode = "pet"
        } else {
            mode = "detail"
            hideTimer.stop()
        }
    }

    Timer {
        id: hideTimer
        interval: petReady ? NewApiPet.bubbleTimeoutSeconds * 1000 : 8000
        repeat: false
        onTriggered: hideBubble()
    }

    Connections {
        target: petReady ? NewApiPet : null
        function onUsageChanged() {
            // 只有余额/今日用量真正变化时才弹气泡,避免每个轮询周期打扰。
            var balance = NewApiPet.balanceText
            var today = NewApiPet.todayText
            var changed = balance !== lastBalance || today !== lastToday
            lastBalance = balance
            lastToday = today
            if (changed) showBubble()
        }
        function onUsageBumped() { petSprite.bounce() }
        function onStatusChanged() {
            if (NewApiPet.hasError && mode !== "detail") showBubble()
        }
    }

    Item {
        id: root
        anchors.fill: parent

        // ------------------------------------------------ 明细卡片
        Rectangle {
            id: detailCard
            visible: petWindow.mode === "detail"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 6
            width: 324
            height: petWindow.detailAreaHeight - 14
            radius: 16
            color: "#F7F9FF"
            border.color: "#D9E1F5"
            border.width: 1

            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8

                Item {
                    width: parent.width
                    height: 24

                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: petReady && NewApiPet.tokenName ? NewApiPet.tokenName : "NewAPI 令牌"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#2B3252"
                        elide: Text.ElideRight
                        width: parent.width - 110
                    }
                    Text {
                        anchors.right: refreshButton.left
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: petReady ? NewApiPet.expiresText : ""
                        font.pixelSize: 11
                        color: "#8A93A6"
                        elide: Text.ElideRight
                        width: 180
                        horizontalAlignment: Text.AlignRight
                    }
                    Rectangle {
                        id: refreshButton
                        anchors.right: closeButton.left
                        anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        width: 44
                        height: 22
                        radius: 11
                        color: refreshArea.pressed ? "#DCE5FF" : (refreshArea.containsMouse ? "#E8EEFF" : "#EDF2FF")
                        Text {
                            anchors.centerIn: parent
                            text: "刷新"
                            font.pixelSize: 12
                            color: "#3E5BD8"
                        }
                        MouseArea {
                            id: refreshArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (petReady) NewApiPet.refresh()
                        }
                    }
                    Rectangle {
                        id: closeButton
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: 44
                        height: 22
                        radius: 11
                        color: closeArea.pressed ? "#E4E7EF" : (closeArea.containsMouse ? "#EEF0F6" : "#F2F4F9")
                        Text {
                            anchors.centerIn: parent
                            text: "收起"
                            font.pixelSize: 12
                            color: "#5B6478"
                        }
                        MouseArea {
                            id: closeArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: petWindow.toggleDetail()
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: "#E3E9F7" }

                Row {
                    width: parent.width
                    spacing: 8

                    Rectangle {
                        width: (parent.width - 16) / 2
                        height: 58
                        radius: 10
                        color: "#FFFFFF"
                        border.color: "#E3E9F7"
                        Column {
                            anchors.centerIn: parent
                            spacing: 2
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "剩余额度"; font.pixelSize: 10; color: "#8A93A6" }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: petReady ? NewApiPet.balanceText : "-"
                                font.pixelSize: 19
                                font.bold: true
                                color: petReady && NewApiPet.lowBalance ? "#D5484A" : "#2F66F4"
                            }
                        }
                    }
                    Rectangle {
                        width: (parent.width - 16) / 2
                        height: 58
                        radius: 10
                        color: "#FFFFFF"
                        border.color: "#E3E9F7"
                        Column {
                            anchors.centerIn: parent
                            spacing: 2
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "今日已用"; font.pixelSize: 10; color: "#8A93A6" }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: petReady ? NewApiPet.todayText.replace("今日已用 ", "") : "-"
                                font.pixelSize: 19
                                font.bold: true
                                color: "#2B3252"
                            }
                        }
                    }
                }

                Row {
                    width: parent.width
                    spacing: 8

                    Text {
                        width: (parent.width - 16) / 2
                        text: petReady ? ("总额度 " + NewApiPet.grantedText) : ""
                        font.pixelSize: 11
                        color: "#5B6478"
                        elide: Text.ElideRight
                    }
                    Text {
                        width: (parent.width - 16) / 2
                        text: petReady ? ("累计已用 " + NewApiPet.usedText) : ""
                        font.pixelSize: 11
                        color: "#5B6478"
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignRight
                    }
                }

                Text {
                    text: "今日 Tokens：" + (petReady ? NewApiPet.todayTokensText : "-")
                    font.pixelSize: 11
                    color: "#5B6478"
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#E3E9F7"
                }

                Text {
                    text: "最近调用"
                    font.pixelSize: 11
                    color: "#8A93A6"
                }

                ListView {
                    id: logList
                    width: parent.width
                    height: parent.height - 218
                    clip: true
                    spacing: 2
                    model: petReady ? NewApiPet.recentLogs : []

                    delegate: Rectangle {
                        width: logList.width
                        height: 30
                        radius: 6
                        color: model.index % 2 === 0 ? "#FFFFFF" : "#F2F5FC"

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.time
                            font.pixelSize: 10
                            color: "#8A93A6"
                        }
                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 76
                            anchors.right: tokenText.left
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.model
                            font.pixelSize: 11
                            color: "#3A4258"
                            elide: Text.ElideRight
                        }
                        Text {
                            id: tokenText
                            anchors.right: quotaText.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.tokens
                            font.pixelSize: 10
                            color: "#8A93A6"
                        }
                        Text {
                            id: quotaText
                            anchors.right: parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.quotaText
                            font.pixelSize: 11
                            font.bold: true
                            color: "#B0762B"
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "暂无调用记录"
                        font.pixelSize: 12
                        color: "#A6ADC0"
                        visible: logList.count === 0
                    }
                }

                Text {
                    text: petReady ? NewApiPet.statusText : ""
                    font.pixelSize: 10
                    color: petReady && NewApiPet.hasError ? "#D5484A" : "#8A93A6"
                    elide: Text.ElideRight
                    width: parent.width
                }
            }
        }

        // ------------------------------------------------ 余额气泡
        Item {
            id: bubble
            visible: petWindow.mode === "bubble"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 4
            width: 300
            height: petWindow.bubbleAreaHeight - 8

            Rectangle {
                id: bubbleBody
                anchors.fill: parent
                radius: 14
                color: "#FFFFFF"
                border.color: petReady && NewApiPet.hasError ? "#F0B9B9" : "#D9E1F5"
                border.width: 1

                Rectangle {
                    id: tail
                    width: 16
                    height: 16
                    radius: 3
                    color: bubbleBody.color
                    border.color: bubbleBody.border.color
                    border.width: 1
                    rotation: 45
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -7
                }

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    anchors.topMargin: 8
                    spacing: 0

                    Text {
                        text: petReady && NewApiPet.tokenName ? NewApiPet.tokenName : "NewAPI 余额"
                        font.pixelSize: 11
                        color: "#8A93A6"
                        elide: Text.ElideRight
                        width: parent.width
                    }
                    Text {
                        text: petReady
                              ? (NewApiPet.hasError ? "连接失败" : (NewApiPet.lowBalance ? "余额已用尽" : NewApiPet.balanceText))
                              : "-"
                        font.pixelSize: 24
                        font.bold: true
                        color: petReady && (NewApiPet.hasError || NewApiPet.lowBalance) ? "#D5484A" : "#2F66F4"
                    }
                    Text {
                        text: petReady
                              ? (NewApiPet.hasError ? NewApiPet.statusText : NewApiPet.todayText)
                              : "-"
                        font.pixelSize: 12
                        color: petReady && NewApiPet.hasError ? "#D5484A" : "#8A93A6"
                        elide: Text.ElideRight
                        width: parent.width
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: petWindow.toggleDetail()
                    cursorShape: Qt.PointingHandCursor
                }
            }
        }

        // ------------------------------------------------ 桌宠本体
        Item {
            id: petSprite
            width: 128
            height: 132
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.bottom: parent.bottom

            function bounce() {
                bounceAnim.restart()
            }

            // 地面阴影
            Rectangle {
                id: groundShadow
                width: 78
                height: 12
                radius: 6
                color: "#1A1B2A4D"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 2
            }

            SequentialAnimation {
                id: bounceAnim
                NumberAnimation { target: bodyGroup; property: "scale"; to: 1.12; duration: 110; easing.type: Easing.OutQuad }
                NumberAnimation { target: bodyGroup; property: "scale"; to: 1.0; duration: 160; easing.type: Easing.OutBack }
            }

            Item {
                id: bodyGroup
                anchors.fill: parent

                SequentialAnimation on y {
                    loops: Animation.Infinite
                    NumberAnimation { to: -4; duration: 1700; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0; duration: 1700; easing.type: Easing.InOutSine }
                }

                // 自定义桌宠图片(可选):配置 pet_image 后替换矢量造型
                Image {
                    visible: petReady && NewApiPet.configPetImage !== ""
                    source: petReady && NewApiPet.configPetImage !== ""
                            ? "file:///" + NewApiPet.configPetImage.replace(/\\/g, "/") : ""
                    anchors.centerIn: parent
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }

                // 矢量小飞宠(未配置图片时显示)
                Item {
                    visible: !petReady || NewApiPet.configPetImage === ""
                    anchors.fill: parent

                    // 信标天线
                    Rectangle {
                        width: 3
                        height: 14
                        radius: 1.5
                        color: "#6C86EC"
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 10
                    }
                    Rectangle {
                        width: 12
                        height: 12
                        radius: 6
                        color: "#FFD166"
                        border.color: "#E8B84B"
                        border.width: 1
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 0

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.35; duration: 900; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                        }
                    }

                    // 身体
                    Rectangle {
                        id: body
                        width: 108
                        height: 92
                        radius: 34
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#93AAFF" }
                            GradientStop { position: 1.0; color: "#6C86EC" }
                        }
                        border.color: petReady && NewApiPet.hasError ? "#E08E8E" : "#5F79D9"
                        border.width: 2
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 24
                    }

                    // 肚皮
                    Rectangle {
                        width: 58
                        height: 42
                        radius: 21
                        color: "#EAF0FF"
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 62
                    }

                    // 眼睛(会眨)
                    Item {
                        id: face
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 52

                        Item {
                            id: eyeLeft
                            x: -22
                            width: 16
                            height: 19

                            Rectangle {
                                anchors.fill: parent
                                radius: 8
                                color: "#FFFFFF"
                            }
                            Rectangle {
                                width: 7
                                height: 9
                                radius: 3.5
                                color: "#2B3252"
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 5
                            }

                            SequentialAnimation on scale {
                                loops: Animation.Infinite
                                PauseAnimation { duration: 3600 }
                                NumberAnimation { to: 0.1; duration: 90 }
                                NumberAnimation { to: 1.0; duration: 90 }
                                PauseAnimation { duration: 3200 }
                            }
                        }
                        Item {
                            id: eyeRight
                            x: 6
                            width: 16
                            height: 19

                            Rectangle {
                                anchors.fill: parent
                                radius: 8
                                color: "#FFFFFF"
                            }
                            Rectangle {
                                width: 7
                                height: 9
                                radius: 3.5
                                color: "#2B3252"
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 5
                            }

                            SequentialAnimation on scale {
                                loops: Animation.Infinite
                                PauseAnimation { duration: 3600 }
                                NumberAnimation { to: 0.1; duration: 90 }
                                NumberAnimation { to: 1.0; duration: 90 }
                                PauseAnimation { duration: 3200 }
                            }
                        }

                        // 腮红
                        Rectangle { x: -34; y: 12; width: 12; height: 6; radius: 3; color: "#66F2A2B6" }
                        Rectangle { x: 22; y: 12; width: 12; height: 6; radius: 3; color: "#66F2A2B6" }

                        // 嘴
                        Rectangle { width: 10; height: 5; radius: 3; color: "#46527A"; y: 12 }
                    }
                }

                // 拖动 / 点击 / 右键交互
                MouseArea {
                    id: petMouse
                    anchors.fill: parent
                    anchors.margins: -6
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    hoverEnabled: true
                    cursorShape: Qt.OpenHandCursor

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
                        if (moved && petReady) {
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
            }
        }

        // ------------------------------------------------ 右键菜单
        // 菜单打开时,点击其他任意位置先关闭菜单
        MouseArea {
            anchors.fill: parent
            visible: contextMenu.visible
            z: 40
            onClicked: contextMenu.visible = false
        }

        Rectangle {
            id: contextMenu
            visible: false
            width: 156
            height: menuColumn.height + 12
            radius: 12
            color: "#FFFFFF"
            border.color: "#D9E1F5"
            border.width: 1
            z: 50

            function openAt() {
                x = Math.max(0, petSprite.x + petSprite.width / 2 - width / 2)
                y = Math.max(0, petSprite.y - height - 6)
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
                            font.pixelSize: 13
                            color: modelData.action === "quit" ? "#C2483F" : "#3A4258"
                        }

                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                contextMenu.visible = false
                                if (modelData.action === "refresh" && petReady) {
                                    NewApiPet.refresh()
                                } else if (modelData.action === "detail") {
                                    petWindow.toggleDetail()
                                } else if (modelData.action === "settings") {
                                    if (managerReady) PetManager.openSettings()
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
}
