pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property string activeWorkspace: "intelligence"

    function pageForWorkspace(key) {
        if (key === "graph")
            return "Graph.qml"
        if (key === "timeline")
            return "Timeline.qml"
        if (key === "intelligence")
            return "Analysis.qml"
        if (key === "map")
            return "MapWorkspace.qml"
        if (key === "media")
            return "MediaWorkspace.qml"
        return ""
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            Layout.minimumHeight: 48
            Layout.maximumHeight: 48
            color: Theme.background

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.divider
            }

            Flickable {
                anchors.fill: parent
                anchors.leftMargin: Spacing.page
                anchors.rightMargin: Spacing.page
                contentWidth: workspaceTabs.width
                contentHeight: height
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                clip: true

                Row {
                    id: workspaceTabs
                    height: parent.height
                    spacing: 6

                    Repeater {
                        model: [
                            { key: "intelligence", label: "Intelligence", icon: "chart.svg", ready: true },
                            { key: "graph", label: "Graph", icon: "graph.svg", ready: true },
                            { key: "timeline", label: "Timeline", icon: "clock.svg", ready: true },
                            { key: "map", label: "Map", icon: "pin_purple.svg", ready: true },
                            { key: "media", label: "Media", icon: "document_blue.svg", ready: true }
                        ]

                        delegate: Rectangle {
                            id: workspaceTab
                            required property var modelData
                            property bool selected: root.activeWorkspace === String(modelData.key)
                            height: 34
                            width: Math.max(92, tabContent.implicitWidth + 28)
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 8
                            color: selected
                                ? Theme.accentSoft
                                : (tabMouse.containsMouse ? Theme.surfaceHover : "transparent")
                            border.width: 1
                            border.color: selected ? Theme.accent : "transparent"

                            Row {
                                id: tabContent
                                anchors.centerIn: parent
                                spacing: 8

                                Image {
                                    width: 16
                                    height: 16
                                    source: "../../assets/icons/" + String(workspaceTab.modelData.icon)
                                    fillMode: Image.PreserveAspectFit
                                    opacity: workspaceTab.selected ? 1.0 : 0.72
                                }

                                Text {
                                    text: String(workspaceTab.modelData.label)
                                    color: workspaceTab.selected ? Theme.textPrimary : Theme.textSecondary
                                    font.pixelSize: 11
                                    font.weight: workspaceTab.selected ? Font.DemiBold : Font.Medium
                                }

                                Rectangle {
                                    visible: !Boolean(workspaceTab.modelData.ready)
                                    width: 6
                                    height: 6
                                    radius: 3
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: Theme.warning
                                }
                            }

                            MouseArea {
                                id: tabMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.activeWorkspace = String(workspaceTab.modelData.key)
                            }

                            ToolTip.visible: tabMouse.containsMouse && !Boolean(workspaceTab.modelData.ready)
                            ToolTip.delay: 450
                            ToolTip.text: "Workspace prepared for the next connector stage"
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Loader {
                anchors.fill: parent
                active: root.pageForWorkspace(root.activeWorkspace).length > 0
                source: root.pageForWorkspace(root.activeWorkspace)
            }


        }
    }
}
