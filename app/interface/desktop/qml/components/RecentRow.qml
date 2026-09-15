import QtQuick
import "../theme"

Item {
    id: root
    property url iconSource
    property color iconColor: Theme.accent
    property string headline: "Finding"
    property string detail: "Detail"
    property string timeText: "2h ago"
    property bool clickable: false
    signal clicked()

    width: parent ? parent.width : 400
    height: 54

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.divider
    }
    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        width: 36
        height: 36
        radius: 7
        color: Qt.rgba(root.iconColor.r, root.iconColor.g, root.iconColor.b, 0.14)
        Image { anchors.centerIn: parent; width: 22; height: 22; source: root.iconSource }
    }
    Text {
        x: 62
        y: 9
        width: parent.width - 150
        text: root.headline
        color: Theme.textPrimary
        elide: Text.ElideRight
        font.pixelSize: 13
        font.weight: Font.Medium
    }
    Text {
        x: 62
        y: 29
        width: parent.width - 150
        text: root.detail
        color: Theme.textMuted
        elide: Text.ElideRight
        font.pixelSize: 11
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: root.clickable ? 31 : 16
        y: 19
        text: root.timeText
        color: Theme.textMuted
        font.pixelSize: 9
    }
    Text {
        visible: root.clickable
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        text: "›"
        color: rowMouse.containsMouse ? Theme.accent : Theme.textMuted
        font.pixelSize: 16
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
