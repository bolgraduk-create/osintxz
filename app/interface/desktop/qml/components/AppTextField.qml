import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: root

    implicitHeight: 42
    leftPadding: 13
    rightPadding: 13
    color: Theme.textPrimary
    placeholderTextColor: Theme.textMuted
    selectionColor: Theme.accent
    selectedTextColor: "#ffffff"
    selectByMouse: true
    hoverEnabled: true
    font.pixelSize: 12

    background: Rectangle {
        radius: 7
        color: "#0d1c28"
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus
            ? Theme.accent
            : (root.hovered ? Theme.borderHover : Theme.border)

        Behavior on border.color { ColorAnimation { duration: Motion.hover } }
    }
}
