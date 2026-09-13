import QtQuick
import "../theme"

Rectangle {
    id: root
    property string symbol: "×"
    property bool dangerHover: false
    signal clicked()

    width: 48
    height: 38
    activeFocusOnTab: enabled
    opacity: enabled ? 1 : 0.44
    color: mouse.pressed
        ? (dangerHover ? "#b9434d" : "#172735")
        : (mouse.containsMouse ? (dangerHover ? "#d94a53" : "#1d2d3c") : "transparent")
    border.width: activeFocus ? 1 : 0
    border.color: activeFocus ? Theme.accent : "transparent"

    Behavior on color { ColorAnimation { duration: 100 } }
    Keys.onReturnPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()

    Text {
        anchors.centerIn: parent
        text: root.symbol
        color: "#b7c6d5"
        font.pixelSize: 17
        font.weight: Font.Light
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: root.forceActiveFocus()
        onClicked: root.clicked()
    }
}
