pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Window

import "components"
import "theme"

ApplicationWindow {
    id: window
    width: 1648
    height: 928
    minimumWidth: 1280
    minimumHeight: 720
    visible: true
    title: "OSINTXZ"
    color: Theme.background
    flags: Qt.Window | Qt.FramelessWindowHint

    property string currentPage: "overview"

    Connections {
        target: desktopBridge
        function onNavigationRequested(page) { window.currentPage = page }
    }

    function pageSource(page: string): string {
        switch (page) {
        case "cases": return "pages/Cases.qml"
        case "search": return "pages/Search.qml"
        case "entities": return "pages/Entities.qml"
        case "graph": return "pages/Graph.qml"
        case "timeline": return "pages/Timeline.qml"
        case "osint": return "pages/Osint.qml"
        case "evidence": return "pages/Evidence.qml"
        case "reports": return "pages/Reports.qml"
        case "settings": return "pages/Settings.qml"
        default: return "pages/Dashboard.qml"
        }
    }

    // Custom title strip, kept very thin to match the concept.
    Rectangle {
        id: titleStrip
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 38
        color: Theme.chrome
        z: 50

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 15
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Repeater {
                model: ["#ff625f", "#f6bd4e", "#44cb6b"]
                delegate: Rectangle {
                    required property var modelData
                    width: 12; height: 12; radius: 6
                    color: modelData
                    opacity: 0.95
                }
            }
        }

        MouseArea {
            anchors.left: parent.left
            anchors.right: windowControls.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            onPressed: window.startSystemMove()
            onDoubleClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized()
        }

        Row {
            id: windowControls
            anchors.right: parent.right
            anchors.top: parent.top
            height: parent.height

            TitleButton { symbol: "−"; onClicked: window.showMinimized() }
            TitleButton {
                symbol: window.visibility === Window.Maximized ? "❐" : "□"
                onClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized()
            }
            TitleButton { symbol: "×"; dangerHover: true; onClicked: window.close() }
        }
    }

    Sidebar {
        id: sidebar
        anchors.left: parent.left
        anchors.top: titleStrip.bottom
        anchors.bottom: parent.bottom
        width: Math.max(228, Math.min(276, window.width * 0.166))
        currentPage: window.currentPage
        systemOnline: desktopBridge.databaseAvailable
        sourceCount: "—"
        integrationCount: "—"
        monitorCount: "—"
        onNavigate: function(page) { window.currentPage = page }
    }

    Item {
        id: mainArea
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: titleStrip.bottom
        anchors.bottom: parent.bottom

        TopBar {
            id: topBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 74
            accountName: desktopBridge.accountDisplayName
            accountRole: desktopBridge.accountRole
            accountInitials: desktopBridge.accountInitials
            databaseOnline: desktopBridge.databaseAvailable
            onOpenCommand: commandPalette.open()
        }

        Loader {
            id: pageLoader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: topBar.bottom
            anchors.bottom: parent.bottom
            source: window.pageSource(window.currentPage)
        }
    }

    CommandPalette {
        id: commandPalette
        parent: Overlay.overlay
        bridge: desktopBridge
    }
}
