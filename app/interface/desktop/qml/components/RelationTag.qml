import QtQuick

Rectangle {
    id: root
    property string label: "LINKED TO"
    implicitWidth: tagText.implicitWidth + 16
    implicitHeight: 20
    radius: 5
    color: "#132435"
    border.color: "#3a5065"
    border.width: 1

    Text {
        id: tagText
        anchors.centerIn: parent
        text: root.label
        color: "#aebdca"
        font.pixelSize: 8
        font.weight: Font.Medium
    }
}
