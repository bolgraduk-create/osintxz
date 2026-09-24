pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../theme"

Rectangle {
    id: root
    property string currentPage: "overview"
    property bool systemOnline: true
    property string sourceCount: "—"
    property string integrationCount: "—"
    property string monitorCount: "—"
    property bool collapsed: false
    signal navigate(string page)

    function activeNavigationKey(page) {
        const key = String(page || "").toLowerCase()
        if (key === "person")
            return "entities"
        if (key === "graph" || key === "timeline" || key === "analysis")
            return "analysis"
        if (key === "registry" || key === "osint")
            return "search"
        if (key === "sources")
            return "settings"
        if (key === "report")
            return "reports"
        return key
    }

    color: Theme.sidebar
    clip: true

    Item {
        id: brandArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 86

        Image {
            id: logo
            x: root.collapsed ? Math.round((parent.width - width) / 2) : 18
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -3
            width: root.collapsed ? 42 : 50
            height: root.collapsed ? 46 : 54
            source: "../../assets/icons/logo_shirt_mark.png"
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            antialiasing: true
            sourceSize.width: 512
            sourceSize.height: 512
        }

        Column {
            anchors.left: logo.right
            anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -7
            visible: !root.collapsed
            spacing: -2

            Row {
                spacing: 0
                Text {
                    text: "OSINT"
                    color: Theme.textPrimary
                    font.pixelSize: 24
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.1
                }
                Text {
                    text: "XZ"
                    color: Theme.accent
                    font.pixelSize: 24
                    font.weight: Font.Bold
                    font.letterSpacing: 1.1
                }
            }

            Text {
                text: "SEE FURTHER"
                color: "#7890a6"
                font.pixelSize: 8
                font.weight: Font.Medium
                font.letterSpacing: 2.0
            }
        }

        Rectangle {
            id: collapseButton
            anchors.right: parent.right
            anchors.rightMargin: root.collapsed ? 18 : 12
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 4
            width: 28
            height: 24
            radius: 6
            color: collapseMouse.containsMouse ? Theme.surfaceRaised : "transparent"
            border.width: 1
            border.color: collapseMouse.containsMouse ? Theme.borderHover : Theme.border

            Text {
                anchors.centerIn: parent
                text: root.collapsed ? "›" : "‹"
                color: Theme.textSecondary
                font.pixelSize: 18
            }

            MouseArea {
                id: collapseMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.collapsed = !root.collapsed
            }

            ToolTip.visible: collapseMouse.containsMouse
            ToolTip.delay: 350
            ToolTip.text: root.collapsed ? "Expand navigation" : "Collapse navigation"
        }
    }

    Column {
        id: nav
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: brandArea.bottom
        anchors.leftMargin: root.collapsed ? 9 : 14
        anchors.rightMargin: root.collapsed ? 9 : 14
        spacing: 3

        Repeater {
            model: [
                { key: "overview", label: "Overview", icon: "home.svg" },
                { key: "cases", label: "Investigations", icon: "folder.svg" },
                { key: "search", label: "Search", icon: "search.svg" },
                { key: "entities", label: "Entities", icon: "users.svg" },
                { key: "analysis", label: "Analysis", icon: "chart.svg" },
                { key: "evidence", label: "Evidence", icon: "document.svg" },
                { key: "reports", label: "Reports", icon: "chart.svg" },
                { key: "settings", label: "Settings", icon: "settings.svg" }
            ]

            delegate: SidebarItem {
                required property var modelData
                width: nav.width
                label: modelData.label
                iconSource: "../../assets/icons/" + modelData.icon
                collapsed: root.collapsed
                selected: root.activeNavigationKey(root.currentPage) === modelData.key
                onClicked: root.navigate(modelData.key)
            }
        }
    }

    Rectangle {
        id: statusPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 58
        height: 132
        radius: 9
        visible: !root.collapsed
        color: statusMouse.containsMouse ? Theme.surfaceRaised : Theme.surface
        border.color: statusMouse.containsMouse ? Theme.borderHover : Theme.border
        border.width: 1

        Behavior on color {
            ColorAnimation { duration: Motion.hover }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            Row {
                spacing: 9
                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: root.systemOnline ? Theme.success : Theme.danger
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: root.systemOnline ? "System Online" : "Database Offline"
                    color: root.systemOnline ? Theme.success : Theme.danger
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
            }

            StatusLine {
                label: "Sources"
                value: root.sourceCount
                iconSource: "../../assets/icons/globe.svg"
            }
            StatusLine {
                label: "Searchable"
                value: root.integrationCount
                iconSource: "../../assets/icons/database.svg"
            }
            StatusLine {
                label: "Active"
                value: root.monitorCount
                iconSource: "../../assets/icons/graph.svg"
            }
        }

        MouseArea {
            id: statusMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.navigate("sources")
        }

        ToolTip.visible: statusMouse.containsMouse
        ToolTip.delay: 450
        ToolTip.text: "Open Source Center"
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        width: 34
        height: 34
        radius: 9
        visible: root.collapsed
        color: compactStatusMouse.containsMouse ? Theme.surfaceRaised : Theme.surface
        border.width: 1
        border.color: compactStatusMouse.containsMouse ? Theme.borderHover : Theme.border

        Rectangle {
            anchors.centerIn: parent
            width: 10
            height: 10
            radius: 5
            color: root.systemOnline ? Theme.success : Theme.danger
        }

        MouseArea {
            id: compactStatusMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.navigate("sources")
        }

        ToolTip.visible: compactStatusMouse.containsMouse
        ToolTip.delay: 350
        ToolTip.text: "Source Center"
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 28
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
        visible: !root.collapsed
        text: "I N T E L L I G E N C E\nF O R   A   S A F E R   T O M O R R O W"
        color: "#536c82"
        font.pixelSize: 7
        lineHeight: 1.55
    }
}
