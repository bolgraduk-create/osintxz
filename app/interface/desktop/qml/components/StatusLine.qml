import QtQuick
import "../theme"

Item {
    id: root
    property string label: "Sources"
    property string value: "0"
    property url iconSource
    width: parent ? parent.width : 200
    height: 17

    Image {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 14
        height: 14
        source: root.iconSource
        opacity: 0.72
    }
    Text {
        anchors.left: parent.left
        anchors.leftMargin: 23
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: Theme.textSecondary
        font.pixelSize: 11
    }
    Text {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: root.value
        color: Theme.textPrimary
        font.pixelSize: 11
        font.weight: Font.DemiBold
    }
}
