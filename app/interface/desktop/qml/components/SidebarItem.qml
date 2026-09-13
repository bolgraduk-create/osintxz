import QtQuick
import "../theme"

Rectangle {
    id: root
    property string label: "Overview"
    property string iconSource: ""
    property bool selected: false
    signal clicked()

    implicitHeight: 48
    radius: 8
    activeFocusOnTab: enabled
    opacity: enabled ? 1 : 0.44
    color: selected
        ? Theme.accentSoft
        : (mouse.pressed ? "#182e3e" : (mouse.containsMouse ? Theme.surfaceRaised : "transparent"))
    border.width: activeFocus ? 1 : 0
    border.color: activeFocus ? Theme.borderHover : "transparent"

    Behavior on color { ColorAnimation { duration: Motion.hover } }
    Keys.onReturnPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()

    Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 4
        height: root.selected ? 34 : 0
        radius: 2
        color: Theme.accent
        Behavior on height { NumberAnimation { duration: Motion.hover; easing.type: Easing.OutCubic } }
    }

    Image {
        id: icon
        anchors.left: parent.left
        anchors.leftMargin: 28
        anchors.verticalCenter: parent.verticalCenter
        width: 23; height: 23
        source: root.iconSource
        fillMode: Image.PreserveAspectFit
        opacity: root.selected ? 1.0 : 0.80
    }

    Text {
        anchors.left: icon.right
        anchors.leftMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: root.selected ? Theme.textPrimary : "#c1cfdb"
        font.pixelSize: 15
        font.weight: root.selected ? Font.DemiBold : Font.Normal
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
