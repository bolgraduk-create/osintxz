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
        case "registry": return "pages/Registry.qml"
        case "entities": return "pages/Entities.qml"
        case "person": return "pages/Person.qml"
        case "graph": return "pages/Graph.qml"
        case "timeline": return "pages/Timeline.qml"
        case "analysis": return "pages/Analysis.qml"
        case "osint": return "pages/Osint.qml"
        case "sources": return "pages/Sources.qml"
        case "evidence": return "pages/Evidence.qml"
        case "reports": return "pages/Reports.qml"
        case "report": return "pages/Report.qml"
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
        sourceCount: String((sourceBridge.sourceCenter.counts || {}).total || 0)
        integrationCount: String((sourceBridge.sourceCenter.counts || {}).searchable || 0)
        monitorCount: sourceBridge.busy ? "1" : "0"
        onNavigate: function(page) { window.currentPage = page }
    }

    Item {
        id: mainArea
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: titleStrip.bottom
        anchors.bottom: parent.bottom

        Image {
            id: worldBackdrop
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 12
            anchors.rightMargin: 8
            anchors.topMargin: 34
            height: Math.min(520, parent.height * 0.62)
            source: "../assets/images/world_network.svg"
            fillMode: Image.PreserveAspectFit
            horizontalAlignment: Image.AlignHCenter
            verticalAlignment: Image.AlignTop
            visible: Boolean(desktopBridge.uiSettings.showWorldMap)
            opacity: window.currentPage === "overview" ? 0.40 : 0.31
            asynchronous: true
            smooth: true
            mipmap: true
            z: 0
        }

        TopBar {
            id: topBar
            z: 2
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
            z: 1
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


