import QtQuick
import "../theme"

Rectangle {
    id: root
    property string title: "Panel"
    property string subtitle: ""
    property url iconSource
    property string actionText: ""
    property int headerHeight: Spacing.panelHeader
    property bool actionButton: false
    property bool showMenu: false
    property bool headerDivider: true
    default property alias contentData: content.data

    radius: Spacing.radius
    color: Theme.surface
    border.color: Theme.border
    border.width: 1

    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.headerHeight

        Image {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.top: parent.top
            anchors.topMargin: root.subtitle === "" ? 15 : 18
            width: 24
            height: 24
            source: root.iconSource
            visible: root.iconSource.toString().length > 0
        }
        Text {
            anchors.left: parent.left
            anchors.leftMargin: root.iconSource.toString().length > 0 ? 54 : 18
            anchors.top: parent.top
            anchors.topMargin: root.subtitle === "" ? 16 : 17
            text: root.title
            color: Theme.textPrimary
            font.pixelSize: Typography.sectionTitle
            font.weight: Font.DemiBold
        }
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 54
            anchors.top: parent.top
            anchors.topMargin: 44
            text: root.subtitle
            color: Theme.textMuted
            font.pixelSize: Typography.secondary
            visible: root.subtitle !== ""
        }

        Rectangle {
            id: actionSurface
            anchors.right: parent.right
            anchors.rightMargin: root.showMenu ? 52 : 16
            anchors.top: parent.top
            anchors.topMargin: root.subtitle === "" ? 12 : 17
            width: root.actionButton ? 174 : actionLabel.implicitWidth
            height: root.actionButton ? 38 : 28
            radius: 7
            color: root.actionButton ? (actionMouse.containsMouse ? Theme.surfaceHover : "#132635") : "transparent"
            border.color: root.actionButton ? Theme.border : "transparent"
            visible: root.actionText !== ""
            Behavior on color { ColorAnimation { duration: Motion.hover } }

            Text {
                id: actionLabel
                anchors.centerIn: parent
                text: root.actionText
                color: actionMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary
                font.pixelSize: 11
            }
            MouseArea {
                id: actionMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
            }
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: 17
            anchors.verticalCenter: actionSurface.verticalCenter
            text: "•••"
            color: Theme.textSecondary
            font.pixelSize: 14
            visible: root.showMenu
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.divider
            visible: root.headerDivider
        }
    }

    Item {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
    }
}
