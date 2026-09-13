import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root

    property bool primary: false
    property bool destructive: false
    property bool quiet: false

    implicitWidth: Math.max(92, label.implicitWidth + 30)
    implicitHeight: 38
    leftPadding: 15
    rightPadding: 15
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    font.pixelSize: 12
    font.weight: Font.DemiBold
    opacity: enabled ? 1 : 0.44

    contentItem: Text {
        id: label
        text: root.text
        color: root.enabled
            ? (root.primary || root.destructive ? "#ffffff" : Theme.textSecondary)
            : Theme.textMuted
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 7
        color: {
            if (!root.enabled)
                return "#13212c"
            if (root.destructive)
                return root.down ? "#b9434d" : (root.hovered ? "#d9535e" : Theme.danger)
            if (root.primary)
                return root.down ? "#245eb7" : (root.hovered ? "#2f75df" : Theme.accent)
            if (root.quiet)
                return root.down ? "#182b3a" : (root.hovered ? Theme.surfaceHover : "transparent")
            return root.down ? "#172a38" : (root.hovered ? Theme.surfaceHover : Theme.surfaceRaised)
        }
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus
            ? Theme.accent
            : (root.primary || root.destructive || root.quiet ? "transparent" : Theme.border)
        scale: root.down && root.enabled ? 0.985 : 1

        Behavior on color { ColorAnimation { duration: Motion.hover } }
        Behavior on border.color { ColorAnimation { duration: Motion.hover } }
        Behavior on scale { NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
    }
}
