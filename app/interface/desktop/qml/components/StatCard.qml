import QtQuick
import "../theme"

Rectangle {
    id: root
    property string title: "Active Cases"
    property string value: "3"
    property string subtext: "1 new case this week"
    property string delta: "50%"
    property url iconSource
    property color accentColor: Theme.accent
    property bool negative: false
    property string chartType: "line"

    implicitHeight: 122
    radius: Spacing.radius
    color: mouse.containsMouse ? Theme.surfaceHover : Theme.surface
    border.color: mouse.containsMouse ? Theme.borderHover : Theme.border
    border.width: 1

    transform: Translate {
        y: mouse.containsMouse ? -2 : 0
        Behavior on y { NumberAnimation { duration: Motion.hover; easing.type: Easing.OutCubic } }
    }
    Behavior on color { ColorAnimation { duration: Motion.hover } }
    Behavior on border.color { ColorAnimation { duration: Motion.hover } }

    Rectangle {
        id: iconBox
        x: 17
        y: 17
        width: 58
        height: 58
        radius: 9
        color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.14)
        Image {
            anchors.centerIn: parent
            width: 31
            height: 31
            source: root.iconSource
        }
    }

    Text {
        x: 84
        y: 21
        text: root.title
        color: Theme.textSecondary
        font.pixelSize: 14
    }

    Row {
        x: 84
        y: 44
        spacing: 14
        Text {
            text: root.value
            color: Theme.textPrimary
            font.pixelSize: Typography.cardValue
            font.weight: Font.DemiBold
        }
        Text {
            anchors.baseline: parent.children[0].baseline
            text: "↑ " + root.delta
            visible: root.delta.length > 0
            color: root.negative ? Theme.danger : Theme.success
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }
    }

    Text {
        x: 17
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        text: root.subtext
        color: Theme.textMuted
        font.pixelSize: 11
    }

    Canvas {
        visible: root.chartType !== "none"
        anchors.right: parent.right
        anchors.rightMargin: 17
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 22
        width: 86
        height: 42

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = root.accentColor
            ctx.fillStyle = Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.32)
            ctx.lineWidth = 1.6
            if (root.chartType === "bars") {
                var values = [10, 17, 25, 34, 28]
                for (var i = 0; i < values.length; ++i)
                    ctx.fillRect(8 + i * 15, height - values[i], 7, values[i])
            } else {
                var ys = [33, 29, 23, 25, 16, 11, 15, 9]
                ctx.beginPath()
                for (var j = 0; j < ys.length; ++j) {
                    var px = 3 + j * (width - 6) / (ys.length - 1)
                    if (j === 0) ctx.moveTo(px, ys[j]); else ctx.lineTo(px, ys[j])
                }
                ctx.stroke()
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.ArrowCursor
    }
}
