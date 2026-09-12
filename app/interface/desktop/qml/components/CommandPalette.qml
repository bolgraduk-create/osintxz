import QtQuick
import QtQuick.Controls
import "../theme"

Popup {
    id: root
    objectName: "commandPalette"
    property var bridge
    property var caseEntries: []
    property var backendResults: []
    width: Math.min(680, Overlay.overlay ? Overlay.overlay.width * 0.55 : 680)
    height: 374
    x: Overlay.overlay ? (Overlay.overlay.width - width) / 2 : 100
    y: Overlay.overlay ? Math.max(92, Overlay.overlay.height * 0.14) : 100
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function reload() {
        if (!bridge) return
        var cases = bridge.pageData("cases", "").records || []
        caseEntries = cases.map(function(item) {
            return { id: item.id, title: item.title, detail: item.detail, kind: "CASE", enabled: true }
        })
        var results = bridge.pageData("search", "").records || []
        backendResults = results.map(function(item) {
            return { id: item.id, title: item.title, detail: item.detail, kind: item.status || "RESULT", enabled: false }
        })
    }

    Connections {
        target: root.bridge
        function onChanged() { root.reload() }
    }

    property var filteredEntries: {
        var query = input.text.trim().toLowerCase()
        if (query.length === 0)
            return caseEntries.slice(0, 5)
        return caseEntries.concat(backendResults).filter(function(entry) {
            return entry.title.toLowerCase().indexOf(query) !== -1 ||
                entry.detail.toLowerCase().indexOf(query) !== -1
        })
    }

    Overlay.modal: Rectangle { color: "#a8050b11" }
    background: Rectangle { color: "#0e1d29"; radius: 12; border.color: Theme.borderHover; border.width: 1 }

    contentItem: Column {
        Rectangle {
            width: parent.width
            height: 66
            color: "transparent"
            Image { x: 20; anchors.verticalCenter: parent.verticalCenter; width: 22; height: 22; source: "../../assets/icons/search.svg" }
            TextInput {
                id: input
                x: 58
                width: parent.width - 128
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.textPrimary
                font.pixelSize: 17
                focus: true
                selectionColor: "#315f9d"
                Keys.onReturnPressed: {
                    if (root.bridge && text.trim().length > 0) {
                        root.bridge.search(text)
                        root.reload()
                    }
                }
            }
            Text { visible: input.text.length === 0; x: 58; anchors.verticalCenter: parent.verticalCenter; text: "Search stored intelligence or open a case..."; color: Theme.textMuted; font.pixelSize: 15 }
            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                width: 38
                height: 24
                radius: 5
                color: "#132637"
                border.color: Theme.border
                Text { anchors.centerIn: parent; text: "ESC"; color: Theme.textSecondary; font.pixelSize: 9 }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.divider }
        }

        Item {
            width: parent.width
            height: 38
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 19
                anchors.verticalCenter: parent.verticalCenter
                text: input.text.length === 0 ? "ACTIVE CASES" : "SEARCH RESULTS"
                color: Theme.textMuted
                font.pixelSize: 9
                font.letterSpacing: 1.8
            }
        }

        Repeater {
            model: root.filteredEntries
            delegate: Rectangle {
                id: resultRow
                required property var modelData
                width: parent.width
                height: 52
                color: rowMouse.containsMouse && rowMouse.enabled ? Theme.surfaceHover : "transparent"
                Behavior on color { ColorAnimation { duration: Motion.hover } }
                Rectangle { x: 19; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 4; color: resultRow.modelData.kind === "CASE" ? Theme.accent : Theme.purple }
                Text { x: 40; y: 9; width: parent.width - 150; elide: Text.ElideRight; text: resultRow.modelData.title; color: Theme.textPrimary; font.pixelSize: 13; font.weight: Font.Medium }
                Text { x: 40; y: 29; width: parent.width - 150; elide: Text.ElideRight; text: resultRow.modelData.detail; color: Theme.textMuted; font.pixelSize: 10 }
                Text { anchors.right: parent.right; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter; text: resultRow.modelData.enabled ? "→" : resultRow.modelData.kind; color: resultRow.modelData.enabled ? Theme.accent : Theme.textMuted; font.pixelSize: 11 }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    enabled: Boolean(resultRow.modelData.enabled)
                    hoverEnabled: true
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (resultRow.modelData.kind === "CASE" && root.bridge) {
                            root.bridge.selectCase(String(resultRow.modelData.id || ""))
                            root.close()
                        }
                    }
                }
            }
        }

        Item {
            width: parent.width
            height: Math.max(0, parent.height - 66 - 38 - root.filteredEntries.length * 52)
            Text {
                anchors.centerIn: parent
                visible: root.filteredEntries.length === 0
                text: input.text.length === 0 ? "No active investigations" : "Press Enter to search stored intelligence"
                color: Theme.textMuted
                font.pixelSize: 12
            }
        }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 }
            NumberAnimation { property: "scale"; from: 0.985; to: 1; duration: 150 }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 110 } }
    onOpened: {
        reload()
        input.clear()
        input.forceActiveFocus()
    }
}
