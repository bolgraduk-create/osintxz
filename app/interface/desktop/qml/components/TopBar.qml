import QtQuick
import "../theme"

Rectangle {
    id: root
    signal openCommand()
    property string accountName: "Local workspace"
    property string accountRole: "No authenticated user"
    property string accountInitials: "LW"
    property bool databaseOnline: true
    color: Theme.background
    border.color: "#172a3a"
    border.width: 0

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.divider
    }

    Rectangle {
        id: searchBox
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(895, Math.max(540, parent.width - 455))
        height: 44
        radius: 8
        color: searchMouse.containsMouse ? Theme.surfaceHover : Theme.surface
        border.color: searchMouse.containsMouse ? Theme.borderHover : Theme.border
        border.width: 1

        Behavior on color { ColorAnimation { duration: Motion.hover } }
        Behavior on border.color { ColorAnimation { duration: Motion.hover } }

        Image { anchors.left: parent.left; anchors.leftMargin: 17; anchors.verticalCenter: parent.verticalCenter; width: 20; height: 20; source: "../../assets/icons/search.svg" }
        Text { anchors.left: parent.left; anchors.leftMargin: 54; anchors.verticalCenter: parent.verticalCenter; text: "Search people, domains, emails, organizations..."; color: Theme.textMuted; font.pixelSize: 14 }
        Rectangle {
            anchors.right: parent.right; anchors.rightMargin: 13; anchors.verticalCenter: parent.verticalCenter
            width: 61; height: 25; radius: 5; color: "#132637"; border.color: "#2b4358"
            Text { anchors.centerIn: parent; text: "Ctrl + K"; color: "#c0cfdd"; font.pixelSize: 11; font.weight: Font.Medium }
        }
        MouseArea { id: searchMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.openCommand() }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        spacing: 28

        TopIcon { source: "../../assets/icons/sun.svg" }
        TopIcon { source: "../../assets/icons/bell.svg"; dotVisible: false }
        TopIcon { source: "../../assets/icons/database.svg"; opacity: root.databaseOnline ? 1 : 0.45 }

        Rectangle { width: 1; height: 32; color: "#263a4c"; anchors.verticalCenter: parent.verticalCenter }

        Rectangle {
            width: 42; height: 42; radius: 21; color: "#3a5068"
            Text { anchors.centerIn: parent; text: root.accountInitials; color: "white"; font.pixelSize: 15; font.weight: Font.DemiBold }
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Text { text: root.accountName; color: "#f3f6f9"; font.pixelSize: 13; font.weight: Font.DemiBold }
            Text { text: root.accountRole; color: "#8ea3b7"; font.pixelSize: 11 }
        }

        Text { text: "⌄"; color: "#a5b7c7"; font.pixelSize: 18; anchors.verticalCenter: parent.verticalCenter }
    }

    Shortcut { sequence: "Ctrl+K"; onActivated: root.openCommand() }
}
