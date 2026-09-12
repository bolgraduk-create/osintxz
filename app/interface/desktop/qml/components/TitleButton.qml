import QtQuick

Rectangle {
    id: root
    property string symbol: "×"
    property bool dangerHover: false
    signal clicked()

    width: 48
    height: 38
    color: mouse.containsMouse ? (dangerHover ? "#d94a53" : "#1d2d3c") : "transparent"

    Behavior on color { ColorAnimation { duration: 100 } }

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
        hoverEnabled: true
        onClicked: root.clicked()
    }
}
