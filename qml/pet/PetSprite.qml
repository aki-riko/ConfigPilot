// 桌宠本体:优先显示内置立绘(可带姿势帧),否则绘制内置矢量小飞宠。
// 交互(拖动/点击/右键)由 PetPanel 的透明层统一处理,这里只负责观感与状态表达。
//
// 组件取舍:桌宠形象是一组插画(内置立绘或用户自备图),PrismQML 没有"角色插画"级别的
// 组件,框架图标集也不包含这个形象,所以形体保留自绘;但语义色(告警角标)改走
// Fluent.Enums,与主程序的状态红同源。
// 身体配色仍是"角色插画"配色(类似图片素材),刻意不随主题切换 —— 这是角色身份
// 的一部分,令牌化会让桌宠在深色主题下变成另一个形象。
//
// 姿势帧状态机(frames 非空时生效):
//   idle    站立,基准姿势
//   blink   空闲时随机插播 170ms,让立绘不再是"贴纸"
//   wave    点击互动 / 从打瞌睡里被叫醒
//   cheer   余额变动(bounce)时举起金币
//   sleepy  90s 无互动后进入,任何交互立刻唤醒
//   alert   余额耗尽/请求失败,优先级最高
// 姿势之间用两层交叉淡入(100ms)而不是硬切:生图各帧的像素不可能逐像素对齐,
// 硬切会看到"跳",交叉淡入把它糊成动作本身。
import QtQuick

import PrismQML as Fluent

Item {
    id: sprite

    // 自定义图片绝对路径(空 = 内置矢量形象)
    property string imagePath: ""
    // 姿势帧表:角色 → 绝对路径(由 backend/pet_art.py 解析预设目录得到)
    property var frames: ({})
    // 错误或余额耗尽时切换配色并弹出警示角标
    property bool alert: false
    property color bodyTopColor: alert ? "#FFA6A6" : "#9FB4FF"
    property color bodyBottomColor: alert ? "#E86A72" : "#6480E8"
    property color bodyBorderColor: alert ? "#D0606A" : "#5A74D6"

    // 基础姿势(可被 sleepy 占据)与一次性姿势(wave/cheer/blink 临时插播)
    property string basePose: "idle"
    property string activePose: ""
    // 交叉淡入用的双缓冲:当前显示的是哪一层
    property int topLayer: 0
    property string shownUrl: ""
    // 打瞌睡阈值与下一次眨眼的间隔
    readonly property int drowsyAfterMs: 90000
    property int blinkEvery: 3200 + Math.round(Math.random() * 2600)

    readonly property bool hasFrames: !!(frames && frames.idle)
    readonly property string poseRole: {
        if (sprite.alert) return "alert"
        if (sprite.activePose !== "") return sprite.activePose
        return sprite.basePose
    }
    // 缺该姿势帧就退回 idle,再退回主立绘路径,最后退回自绘矢量形体。
    readonly property string shownPath: {
        var table = sprite.frames
        var path = (table && table[sprite.poseRole]) ? table[sprite.poseRole] : ""
        if (path === "" && table && table.idle) path = table.idle
        return path !== "" ? path : sprite.imagePath
    }

    implicitWidth: 120
    implicitHeight: 128

    function _urlOf(path) {
        return path !== "" ? "file:///" + String(path).replace(/\\/g, "/") : ""
    }

    function _hasFrame(role) {
        return !!(sprite.frames && sprite.frames[role])
    }

    function _applyFrame(path) {
        var url = sprite._urlOf(path)
        if (url === sprite.shownUrl) return
        sprite.shownUrl = url
        var next = sprite.topLayer === 0 ? poseB : poseA
        var current = sprite.topLayer === 0 ? poseA : poseB
        next.source = url
        next.opacity = 1
        current.opacity = 0
        sprite.topLayer = 1 - sprite.topLayer
    }

    // 播放一次性姿势;没有对应帧就什么都不做(单图形象同样能正常互动)。
    function playPose(role, holdMs) {
        if (!sprite._hasFrame(role)) return
        sprite.activePose = role
        poseTimer.interval = Math.max(120, holdMs)
        poseTimer.restart()
    }

    // 有交互:刷新空闲计时,睡着的话先挥手醒过来。
    // 不用 Timer.restart() —— running 是绑定表达式,命令式 start/stop 会把绑定打断。
    function poke() {
        sprite.lastInteraction = Date.now()
        if (sprite.basePose === "sleepy") {
            sprite.basePose = "idle"
            sprite.playPose("wave", 1100)
        }
    }
    property double lastInteraction: 0

    // 拖动时前倾/后仰(由 PetPanel 按横向速度驱动,松手归零)
    function lean(angle) {
        sprite.dragLean = Math.max(-12, Math.min(12, angle))
    }
    property real dragLean: 0
    // 站立时的轻微左右摇摆(与上下浮动错开周期,避免合成"画圈")
    property real sway: 0
    Behavior on dragLean {
        NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
    }

    // 原地挤压拉伸:压扁 → 拉长 → 回弹,比等比缩放更有"肉感"。
    function bounce() {
        bounceAnim.restart()
        sprite.playPose("cheer", 1200)
    }

    onShownPathChanged: sprite._applyFrame(sprite.shownPath)
    // 初始那次求值不会发 changed 信号,必须显式落一次,否则第一帧永远不显示。
    Component.onCompleted: {
        sprite.lastInteraction = Date.now()
        sprite._applyFrame(sprite.shownPath)
    }
    onAlertChanged: sprite.lastInteraction = Date.now()
    onActivePoseChanged: {
        if (sprite.activePose === "") sprite.lastInteraction = Date.now()
    }

    // 地面阴影(呼吸幅度与本体相反,增强"离地飘浮"的感觉)
    Rectangle {
        id: groundShadow
        width: 72
        height: 11
        radius: 6
        color: "#22171C3A"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 1

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { to: 0.55; duration: 1800; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.95; duration: 1800; easing.type: Easing.InOutSine }
        }
    }

    ParallelAnimation {
        id: bounceAnim

        // target/property 只能写在 NumberAnimation 上(SequentialAnimation 不是
        // PropertyAnimation,没有这两个属性)。
        SequentialAnimation {
            NumberAnimation {
                target: bodyTransform; property: "xScale"
                to: 1.16; duration: 90; easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: bodyTransform; property: "xScale"
                to: 0.93; duration: 120; easing.type: Easing.InOutQuad
            }
            NumberAnimation {
                target: bodyTransform; property: "xScale"
                to: 1.0; duration: 150; easing.type: Easing.OutBack
            }
        }
        SequentialAnimation {
            NumberAnimation {
                target: bodyTransform; property: "yScale"
                to: 0.86; duration: 90; easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: bodyTransform; property: "yScale"
                to: 1.11; duration: 120; easing.type: Easing.InOutQuad
            }
            NumberAnimation {
                target: bodyTransform; property: "yScale"
                to: 1.0; duration: 150; easing.type: Easing.OutBack
            }
        }
    }

    SequentialAnimation on sway {
        loops: Animation.Infinite
        NumberAnimation { to: 2.2; duration: 2600; easing.type: Easing.InOutSine }
        NumberAnimation { to: -2.2; duration: 2600; easing.type: Easing.InOutSine }
    }

    // 眨眼:只在真正空闲(没有一次性姿势、没告警、没打瞌睡)时插播
    Timer {
        id: blinkTimer
        interval: sprite.blinkEvery
        repeat: true
        running: sprite.hasFrames && !sprite.alert
                 && sprite.basePose === "idle" && sprite._hasFrame("blink")
        onTriggered: {
            sprite.blinkEvery = 3200 + Math.round(Math.random() * 2600)
            // 220ms 而不是 170ms:交叉淡入进出各 100ms,太短闭眼还没显形就淡回去了
            if (sprite.activePose === "") sprite.playPose("blink", 220)
        }
    }

    // 久无互动 → 打瞌睡;pet 形态下不该一直瞪着屏幕。
    // 用固定节拍 + 时间戳判断,而不是"到点触发再 restart":running 一旦是绑定,
    // restart() 会打断绑定;5s 一跳的开销可忽略。
    Timer {
        id: drowsyTimer
        interval: 5000
        repeat: true
        running: sprite.hasFrames && sprite._hasFrame("sleepy")
        onTriggered: {
            if (sprite.alert || sprite.activePose !== "" || sprite.basePose !== "idle") return
            if (Date.now() - sprite.lastInteraction > sprite.drowsyAfterMs)
                sprite.basePose = "sleepy"
        }
    }

    Timer {
        id: poseTimer
        onTriggered: sprite.activePose = ""
    }

    Item {
        id: bodyGroup
        anchors.fill: parent
        anchors.bottomMargin: 10
        // 挤压拉伸以脚底为原点,才像"站在地上被压扁"而不是整张图放大
        transformOrigin: Item.Bottom
        // 非等比缩放要用具体的 Scale(Transform 是抽象基类,不能实例化)
        transform: Scale {
            id: bodyTransform
            xScale: 1.0
            yScale: 1.0
        }
        rotation: sprite.dragLean + sprite.sway

        SequentialAnimation on y {
            loops: Animation.Infinite
            NumberAnimation { from: 2; to: -5; duration: 1900; easing.type: Easing.InOutSine }
            NumberAnimation { from: -5; to: 2; duration: 1900; easing.type: Easing.InOutSine }
        }

        // ------------------------------------------------ 立绘(双缓冲交叉淡入)
        Image {
            id: poseA
            anchors.fill: parent
            opacity: 0
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }
        Image {
            id: poseB
            anchors.fill: parent
            opacity: 0
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }

        // ------------------------------------------------ 内置矢量形象
        Item {
            anchors.fill: parent
            visible: sprite.shownUrl === ""

            // 信标天线
            Rectangle {
                width: 3
                height: 15
                radius: 1.5
                color: sprite.alert ? "#E39AA0" : "#7C93F0"
                anchors.horizontalCenter: parent.horizontalCenter
                y: 12
            }
            Rectangle {
                width: 13
                height: 13
                radius: 6.5
                color: sprite.alert ? "#FF9A8B" : "#FFD166"
                border.color: sprite.alert ? "#E37F73" : "#E8B84B"
                border.width: 1
                anchors.horizontalCenter: parent.horizontalCenter
                y: 1

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
                height: 94
                radius: 34
                anchors.horizontalCenter: parent.horizontalCenter
                y: 25
                gradient: Gradient {
                    GradientStop { position: 0.0; color: sprite.bodyTopColor }
                    GradientStop { position: 1.0; color: sprite.bodyBottomColor }
                }
                border.color: sprite.bodyBorderColor
                border.width: 2
            }

            // 肚皮
            Rectangle {
                width: 58
                height: 42
                radius: 21
                color: "#F2F6FF"
                anchors.horizontalCenter: parent.horizontalCenter
                y: 64
            }

            // 表情
            Item {
                id: face
                anchors.horizontalCenter: parent.horizontalCenter
                y: 53

                Repeater {
                    // 两只眼睛:结构完全一致,仅横向位置不同,眨眼动画各自独立。
                    model: [-22, 6]

                    delegate: Item {
                        x: modelData
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
                }

                // 腮红
                Rectangle { x: -34; y: 12; width: 12; height: 6; radius: 3; color: "#66F2A2B6" }
                Rectangle { x: 22; y: 12; width: 12; height: 6; radius: 3; color: "#66F2A2B6" }

                // 嘴:常态是微笑弧,异常时变成波浪嘴
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: sprite.alert ? 12 : 10
                    text: sprite.alert ? "﹏" : "◡"
                    font.pixelSize: 15
                    font.bold: true
                    color: "#46527A"
                }
            }
        }

        // ------------------------------------------------ 警示角标
        Rectangle {
            id: badge
            width: 22
            height: 22
            radius: 11
            color: Fluent.Enums.statusLevel.errorColor
            border.color: Fluent.Enums.surfaceColor
            border.width: 2
            visible: opacity > 0.01
            opacity: sprite.alert ? 1 : 0
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.top: parent.top
            anchors.topMargin: 0

            Behavior on opacity { NumberAnimation { duration: 180 } }

            Text {
                anchors.centerIn: parent
                text: "!"
                font.pixelSize: 13
                font.bold: true
                color: "#FFFFFF"
            }
        }
    }
}
