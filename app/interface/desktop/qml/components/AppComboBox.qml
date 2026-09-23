pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../theme"

ComboBox {
    id: root

    implicitHeight: 42
    leftPadding: 13
    rightPadding: 38
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    font.pixelSize: 12

    contentItem: Text {
        leftPadding: 13
        rightPadding: 36
        text: root.displayText
        color: root.enabled ? Theme.textPrimary : Theme.textMuted
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: root.width - width - 14
        anchors.verticalCenter: parent.verticalCenter
        text: "⌄"
        color: root.enabled ? Theme.textSecondary : Theme.textMuted
        font.pixelSize: 17
    }

    background: Rectangle {
        radius: 7
        color: root.down ? "#132735" : "#0d1c28"
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus
            ? Theme.accent
            : (root.hovered ? Theme.borderHover : Theme.border)

        Behavior on color { ColorAnimation { duration: Motion.hover } }
        Behavior on border.color { ColorAnimation { duration: Motion.hover } }
    }

    delegate: ItemDelegate {
        id: option
        required property var modelData
        required property int index
        width: root.width - 12
        height: 38
        text: root.textAt(option.index)
        highlighted: root.highlightedIndex === option.index
        hoverEnabled: true
        font.pixelSize: 12
        contentItem: Text {
            text: option.text
            color: Theme.textPrimary
            font: option.font
            verticalAlignment: Text.AlignVCenter
            leftPadding: 10
        }
        background: Rectangle {
            radius: 6
            color: option.down
                ? "#183044"
                : (option.highlighted || option.hovered ? Theme.surfaceHover : "transparent")
        }
    }

    popup: Popup {
        objectName: "appComboBoxPopup"
        y: root.height + 5
        width: root.width
        implicitHeight: Math.min(contentItem.implicitHeight + 12, 260)
        padding: 6

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            color: Theme.surfaceRaised
            radius: 8
            border.color: Theme.borderHover
            border.width: 1
        }
    }
}
