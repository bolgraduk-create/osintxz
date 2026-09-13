import QtQuick
import QtQuick.Controls
import "../theme"

Popup {
    id: root

    default property alias dialogContent: dialogBody.data
    property string title: "Dialog"
    property string description: ""
    property string primaryText: "Continue"
    property string cancelText: "Cancel"
    property bool primaryEnabled: true
    property bool destructive: false
    property int bodyHeight: 120

    signal accepted()
    signal rejected()

    function accept() {
        if (!primaryEnabled)
            return
        close()
        accepted()
    }

    function reject() {
        close()
        rejected()
    }

    parent: Overlay.overlay
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    height: 72 + bodyHeight + 68
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.NoAutoClose

    Overlay.modal: Rectangle {
        color: "#a8050b11"
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }

    background: Rectangle {
        color: Theme.surface
        radius: 10
        border.color: Theme.borderHover
        border.width: 1
    }

    contentItem: Item {
        Shortcut {
            sequence: "Esc"
            context: Qt.WindowShortcut
            enabled: root.opened
            onActivated: root.reject()
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 72
            color: "transparent"

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 22
                anchors.right: closeButton.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Text {
                    width: parent.width
                    text: root.title
                    color: Theme.textPrimary
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: root.description.length > 0
                    text: root.description
                    color: Theme.textMuted
                    font.pixelSize: 10
                    elide: Text.ElideRight
                }
            }

            AppButton {
                id: closeButton
                objectName: "dialogCloseButton"
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 34
                height: 34
                implicitWidth: 34
                implicitHeight: 34
                text: "×"
                quiet: true
                onClicked: root.reject()
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.divider
            }
        }

        Item {
            id: dialogBody
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 72
            height: root.bodyHeight
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 68
            color: "#0e1d29"
            radius: 10

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Theme.divider
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 10
                color: parent.color
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                AppButton {
                    objectName: "dialogCancelButton"
                    text: root.cancelText
                    onClicked: root.reject()
                }
                AppButton {
                    objectName: "dialogPrimaryButton"
                    text: root.primaryText
                    primary: !root.destructive
                    destructive: root.destructive
                    enabled: root.primaryEnabled
                    onClicked: root.accept()
                }
            }
        }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: 150; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 110; easing.type: Easing.InCubic }
            NumberAnimation { property: "scale"; from: 1; to: 0.99; duration: 110; easing.type: Easing.InCubic }
        }
    }
}
