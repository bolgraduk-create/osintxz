pragma ComponentBehavior: Bound
import QtQuick
import "../theme"

Rectangle {
    id: root
    property string currentPage: "overview"
    property bool systemOnline: true
    property string sourceCount: "—"
    property string integrationCount: "—"
    property string monitorCount: "—"
    signal navigate(string page)

    color: Theme.sidebar

    Column {
        anchors.fill: parent
        anchors.leftMargin: 15
        anchors.rightMargin: 15

        Item {
            width: parent.width
            height: 93

            Image {
                id: logo
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -5
                width: 56; height: 60
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
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -10
                spacing: -2
                Row {
                    spacing: 0
                    Text { text: "OSINT"; color: Theme.textPrimary; font.pixelSize: 27; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                    Text { text: "XZ"; color: Theme.accent; font.pixelSize: 27; font.weight: Font.Bold; font.letterSpacing: 1.2 }
                }
                Text { text: "SEE FURTHER"; color: "#7890a6"; font.pixelSize: 9; font.weight: Font.Medium; font.letterSpacing: 2.3 }
            }
        }

        Column {
            id: nav
            width: parent.width
            spacing: 2

            Repeater {
                model: [
                    {key:"overview", label:"Overview", icon:"home.svg"},
                    {key:"cases", label:"Cases", icon:"folder.svg"},
                    {key:"search", label:"Search", icon:"search.svg"},
                    {key:"entities", label:"Entities", icon:"users.svg"},
                    {key:"graph", label:"Graph", icon:"graph.svg"},
                    {key:"timeline", label:"Timeline", icon:"clock.svg"},
                    {key:"osint", label:"OSINT", icon:"globe.svg"},
                    {key:"sources", label:"Sources", icon:"database.svg"},
                    {key:"evidence", label:"Evidence", icon:"document.svg"},
                    {key:"reports", label:"Reports", icon:"chart.svg"},
                    {key:"settings", label:"Settings", icon:"settings.svg"}
                ]

                delegate: SidebarItem {
                    required property var modelData
                    width: nav.width
                    label: modelData.label
                    iconSource: "../../assets/icons/" + modelData.icon
                    selected: root.currentPage === modelData.key
                    onClicked: root.navigate(modelData.key)
                }
            }
        }
    }

    Rectangle {
        id: statusPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 78
        height: 142
        radius: 9
        color: Theme.surface
        border.color: Theme.border
        border.width: 1

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Row {
                spacing: 9
                Rectangle { width: 11; height: 11; radius: 6; color: root.systemOnline ? Theme.success : Theme.danger; anchors.verticalCenter: parent.verticalCenter }
                Text { text: root.systemOnline ? "System Online" : "Database Offline"; color: root.systemOnline ? Theme.success : Theme.danger; font.pixelSize: 13; font.weight: Font.DemiBold }
            }
            StatusLine { label: "OSINT Connectors"; value: root.sourceCount; iconSource: "../../assets/icons/globe.svg" }
            StatusLine { label: "Integrations"; value: root.integrationCount; iconSource: "../../assets/icons/database.svg" }
            StatusLine { label: "Active Monitors"; value: root.monitorCount; iconSource: "../../assets/icons/graph.svg" }
        }
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 32
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 21
        text: "I N T E L L I G E N C E\nF O R   A   S A F E R   T O M O R R O W"
        color: "#536c82"
        font.pixelSize: 8
        lineHeight: 1.7
    }
}
