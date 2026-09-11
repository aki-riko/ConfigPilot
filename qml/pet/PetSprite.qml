// 桌宠本体:优先显示用户在设置里配置的图片,否则绘制内置矢量小飞宠。
// 交互(拖动/点击/右键)由 PetWindow 的透明层统一处理,这里只负责观感与状态表达。
import QtQuick

Item {
    id: sprite

    // 自定义图片绝对路径(空 = 内置矢量形象)
    property string imagePath: ""
    // 错误或余额耗尽时切换配色并弹出警示角标
    property bool alert: false
    property color bodyTopColor: alert ? "#FFA6A6" : "#9FB4FF"
    property color bodyBottomColor: alert ? "#E86A72" : "#6480E8"
    property color bodyBorderColor: alert ? "#D0606A" : "#5A74D6"

    implicitWidth: 120
    implicitHeight: 128

    function bounce() {
        bounceAnim.restart()
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

    SequentialAnimation {
        id: bounceAnim
        NumberAnimation {
            target: bodyGroup
            property: "scale"
            to: 1.14
            duration: 110
            easing.type: Easing.OutQuad
        }
        NumberAnimation {
            target: bodyGroup
            property: "scale"
            to: 1.0
            duration: 180
            easing.type: Easing.OutBack
        }
    }

    Item {
        id: bodyGroup
        anchors.fill: parent
        anchors.bottomMargin: 10

        SequentialAnimation on y {
            loops: Animation.Infinite
            NumberAnimation { from: 2; to: -5; duration: 1900; easing.type: Easing.InOutSine }
            NumberAnimation { from: -5; to: 2; duration: 1900; easing.type: Easing.InOutSine }
        }

        // ------------------------------------------------ 自定义图片模式
        Image {
            anchors.fill: parent
            visible: sprite.imagePath !== ""
            source: sprite.imagePath !== ""
                    ? "file:///" + sprite.imagePath.replace(/\\/g, "/") : ""
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
        }

        // ------------------------------------------------ 内置矢量形象
        Item {
            anchors.fill: parent
            visible: sprite.imagePath === ""

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
            color: "#E0565B"
            border.color: "#FFFFFF"
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
