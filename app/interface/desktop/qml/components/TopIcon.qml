import QtQuick

Item {
    id: root
    property url source
    property bool dotVisible: false
    width: 27; height: 30

    Image { anchors.centerIn: parent; width: 22; height: 22; source: root.source; opacity: 0.88 }
    Rectangle { visible: root.dotVisible; width: 7; height: 7; radius: 4; color: "#3f82f7"; anchors.right: parent.right; anchors.top: parent.top }
}
