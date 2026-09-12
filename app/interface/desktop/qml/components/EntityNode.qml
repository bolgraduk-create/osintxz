import QtQuick
import "../theme"

Item {
    id: root
    property string title: "Entity"
    property string subtitle: "Type"
    property url iconSource
    property color nodeColor: Theme.accent
    property bool central: false
    property string labelSide: "right"
    property real nodeX: 0
    property real nodeY: 0

    readonly property real markerSize: central ? 112 : 50
    readonly property real markerCenterX: central || labelSide === "below"
        ? width / 2
        : (labelSide === "left" ? width - markerSize / 2 : markerSize / 2)
    readonly property real markerCenterY: labelSide === "below" || central
        ? markerSize / 2
        : height / 2

    width: central ? 190 : (labelSide === "below" ? 164 : 220)
    height: central ? 160 : (labelSide === "below" ? 88 : 64)
    x: nodeX - markerCenterX
    y: nodeY - markerCenterY

    transform: Scale {
        origin.x: root.markerCenterX
        origin.y: root.markerCenterY
        xScale: mouse.containsMouse ? 1.025 : 1
        yScale: xScale
        Behavior on xScale { NumberAnimation { duration: Motion.hover; easing.type: Easing.OutCubic } }
        Behavior on yScale { NumberAnimation { duration: Motion.hover; easing.type: Easing.OutCubic } }
    }

    Rectangle {
        id: marker
        x: root.central || root.labelSide === "below"
            ? (root.width - width) / 2
            : (root.labelSide === "left" ? root.width - width : 0)
        y: root.central || root.labelSide === "below" ? 0 : (root.height - height) / 2
        width: root.markerSize
        height: width
        radius: width / 2
        color: "#102333"
        border.color: root.nodeColor
        border.width: root.central ? 4 : 2
        clip: true

        Canvas {
            anchors.fill: parent
            anchors.margins: 4
            visible: root.central
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var bg = ctx.createLinearGradient(0, 0, width, height)
                bg.addColorStop(0, "#3c4855")
                bg.addColorStop(1, "#111922")
                ctx.fillStyle = bg
                ctx.beginPath()
                ctx.arc(width / 2, height / 2, width / 2, 0, Math.PI * 2)
                ctx.fill()

                ctx.fillStyle = "#1d2731"
                ctx.beginPath()
                ctx.moveTo(17, height)
                ctx.bezierCurveTo(21, 79, 37, 71, 51, 70)
                ctx.bezierCurveTo(70, 71, 87, 81, 91, height)
                ctx.closePath()
                ctx.fill()

                ctx.fillStyle = "#8d969e"
                ctx.fillRect(44, 61, 20, 22)
                ctx.save()
                ctx.translate(54, 45)
                ctx.scale(0.74, 1)
                ctx.fillStyle = "#b5bcc2"
                ctx.beginPath()
                ctx.arc(0, 0, 27, 0, Math.PI * 2)
                ctx.fill()
                ctx.restore()

                ctx.fillStyle = "#171e25"
                ctx.beginPath()
                ctx.moveTo(32, 39)
                ctx.bezierCurveTo(33, 13, 51, 8, 65, 14)
                ctx.bezierCurveTo(78, 19, 80, 32, 74, 43)
                ctx.bezierCurveTo(69, 29, 57, 26, 45, 27)
                ctx.bezierCurveTo(42, 33, 37, 37, 32, 39)
                ctx.fill()

                ctx.strokeStyle = "#414951"
                ctx.lineWidth = 2
                ctx.beginPath()
                ctx.moveTo(43, 47); ctx.lineTo(49, 46)
                ctx.moveTo(60, 46); ctx.lineTo(66, 47)
                ctx.moveTo(53, 49); ctx.lineTo(52, 59); ctx.lineTo(56, 60)
                ctx.moveTo(47, 67); ctx.bezierCurveTo(52, 70, 58, 70, 63, 66)
                ctx.stroke()

                ctx.strokeStyle = "#c0c6cb"
                ctx.lineWidth = 2
                ctx.beginPath()
                ctx.moveTo(44, 79); ctx.lineTo(54, 91); ctx.lineTo(65, 79)
                ctx.stroke()
            }
        }

        Image {
            anchors.centerIn: parent
            width: 28
            height: 28
            source: root.iconSource
            fillMode: Image.PreserveAspectFit
            visible: !root.central && root.iconSource.toString().length > 0
        }
    }

    Column {
        id: labelColumn
        x: root.central || root.labelSide === "below"
            ? 0
            : (root.labelSide === "left" ? 0 : marker.x + marker.width + 12)
        y: root.central || root.labelSide === "below"
            ? marker.y + marker.height + (root.central ? 7 : 5)
            : (root.height - height) / 2
        width: root.central || root.labelSide === "below"
            ? root.width
            : root.width - marker.width - 12
        spacing: root.central ? 4 : 2

        Text {
            width: parent.width
            text: root.title
            color: Theme.textPrimary
            horizontalAlignment: root.labelSide === "left" ? Text.AlignRight :
                ((root.central || root.labelSide === "below") ? Text.AlignHCenter : Text.AlignLeft)
            elide: Text.ElideRight
            font.pixelSize: root.central ? 16 : 12
            font.weight: root.central ? Font.DemiBold : Font.Medium
        }

        Rectangle {
            anchors.horizontalCenter: root.central ? parent.horizontalCenter : undefined
            width: root.central ? subtitleText.implicitWidth + 20 : parent.width
            height: root.central ? 24 : 16
            radius: 7
            color: root.central ? "#194686" : "transparent"

            Text {
                id: subtitleText
                anchors.centerIn: root.central ? parent : undefined
                anchors.left: root.central ? undefined : parent.left
                anchors.right: root.central ? undefined : parent.right
                text: root.subtitle
                color: root.central ? "#d7e6ff" : Theme.textSecondary
                horizontalAlignment: root.labelSide === "left" ? Text.AlignRight :
                    ((root.labelSide === "below") ? Text.AlignHCenter : Text.AlignLeft)
                elide: Text.ElideRight
                font.pixelSize: root.central ? 11 : 10
                font.weight: root.central ? Font.Medium : Font.Normal
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
