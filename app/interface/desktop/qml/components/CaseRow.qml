import QtQuick
import "../theme"

Item {
    id: root
    property string name: "Case"
    property string detail: "Description"
    property string priority: "Low"
    property color priorityColor: "#6d91ad"
    property string timeText: "Updated 1d ago"
    property color folderColor: Theme.accent
    property string caseId: ""
    property bool clickable: true
    signal clicked()
    width: parent ? parent.width : 400
    height: 51

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.divider
    }

    Canvas {
        x: 18
        anchors.verticalCenter: parent.verticalCenter
        width: 24
        height: 20
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.fillStyle = root.folderColor
            ctx.beginPath()
            ctx.roundedRect(1, 4, 22, 15, 3, 3)
            ctx.fill()
            ctx.fillRect(3, 1, 9, 6)
        }
    }

    Text {
        x: 55
        y: 9
        width: parent.width - 280
        text: root.name
        color: Theme.textPrimary
        elide: Text.ElideRight
        font.pixelSize: 13
        font.weight: Font.Medium
    }
    Text {
        x: 55
        y: 28
        width: parent.width - 280
        text: root.detail
        color: Theme.textMuted
        elide: Text.ElideRight
        font.pixelSize: 10
    }

    Rectangle {
        anchors.right: timeLabel.left
        anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        width: 72
        height: 28
        radius: 7
        color: Qt.rgba(root.priorityColor.r, root.priorityColor.g, root.priorityColor.b, 0.14)
        border.color: Qt.rgba(root.priorityColor.r, root.priorityColor.g, root.priorityColor.b, 0.38)
        Text {
            anchors.centerIn: parent
            text: root.priority
            color: root.priorityColor
            font.pixelSize: 10
            font.weight: Font.Medium
        }
    }
    Text {
        id: timeLabel
        anchors.right: moreLabel.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        text: root.timeText
        color: Theme.textMuted
        font.pixelSize: 9
    }
    Text {
        id: moreLabel
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        text: "•••"
        color: Theme.textSecondary
        font.pixelSize: 11
        font.letterSpacing: 1
    }

    MouseArea {
        id: rowMouse
        anchors.fill: parent
        enabled: root.clickable
        hoverEnabled: true
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
}
