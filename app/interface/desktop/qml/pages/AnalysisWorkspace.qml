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
                            { key: "map", label: "Map", icon: "pin_purple.svg", ready: false },
                            { key: "media", label: "Media", icon: "document_blue.svg", ready: false }
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

            Item {
                anchors.fill: parent
                visible: root.activeWorkspace === "map" || root.activeWorkspace === "media"

                Column {
                    anchors.centerIn: parent
                    width: Math.min(560, parent.width - 80)
                    spacing: 14

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 58
                        height: 58
                        radius: 14
                        color: Theme.accentSoft
                        border.width: 1
                        border.color: Theme.borderHover

                        Image {
                            anchors.centerIn: parent
                            width: 28
                            height: 28
                            source: root.activeWorkspace === "map"
                                ? "../../assets/icons/pin_purple.svg"
                                : "../../assets/icons/document_blue.svg"
                            fillMode: Image.PreserveAspectFit
                        }
                    }

                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: root.activeWorkspace === "map"
                            ? "Map workspace"
                            : "Media workspace"
                        color: Theme.textPrimary
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                    }

                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.activeWorkspace === "map"
                            ? "Prepared for entity locations, evidence points, GEO enrichment, satellite layers and time-aware map analysis."
                            : "Prepared for images, video and audio with metadata, OCR, face analysis, transcription, similarity and external media pivots."
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        lineHeight: 1.4
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: readyLabel.implicitWidth + 28
                        height: 28
                        radius: 7
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border

                        Text {
                            id: readyLabel
                            anchors.centerIn: parent
                            text: "FOUNDATION READY · DATA CONNECTION NEXT"
                            color: Theme.textMuted
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.8
                        }
                    }
                }
            }
        }
    }
}
