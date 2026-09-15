pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var graph: desktopBridge.graphWorkspace || ({})
    property var stats: graph.statistics || ({})
    property var options: graph.options || []
    property var relationshipTypes: stats.relationshipTypes || []

    function reload() {
        root.graph = desktopBridge.graphWorkspace || ({})
        root.stats = root.graph.statistics || ({})
        root.options = root.graph.options || []
        root.relationshipTypes = root.stats.relationshipTypes || []
    }

    function optionLabels() {
        var labels = []
        for (var i = 0; i < root.options.length; ++i)
            labels.push(String(root.options[i].label || "Unnamed entity"))
        return labels
    }

    function focusIndex() {
        var focus = String(root.graph.focusId || "")
        for (var i = 0; i < root.options.length; ++i) {
            if (String(root.options[i].id || "") === focus)
                return i
        }
        return root.options.length > 0 ? 0 : -1
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.reload() }
    }

    Component.onCompleted: root.reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 16
        anchors.bottomMargin: 24
        spacing: Spacing.panelGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 76

            Text {
                x: 2; y: 0
                text: "RELATIONSHIP ANALYSIS"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 2; y: 19
                text: "Relationship Graph"
                color: Theme.textPrimary
                font.pixelSize: Typography.pageTitle
                font.weight: Font.DemiBold
            }
            Text {
                x: 3; y: 54
                text: desktopBridge.hasCurrentCase
                    ? "Explore persisted entity relationships in " + desktopBridge.currentCaseTitle + "."
                    : "Select an investigation to inspect relationships."
                color: Theme.textSecondary
                font.pixelSize: 12
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 122
            spacing: Spacing.panelGap

            StatCard {
                Layout.fillWidth: true
                title: "Nodes"
                value: String(root.stats.nodeCount || 0)
                delta: ""
                subtext: "Entities in current investigation"
                iconSource: "../../assets/icons/graph_blue.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Relationships"
                value: String(root.stats.edgeCount || 0)
                delta: ""
                subtext: "Persisted entity-to-entity links"
                iconSource: "../../assets/icons/graph_blue.svg"
                accentColor: Theme.cyan
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Connected"
                value: String(root.stats.connectedNodes || 0)
                delta: ""
                subtext: "Entities with at least one link"
                iconSource: "../../assets/icons/users_cyan.svg"
                accentColor: Theme.success
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Isolated"
                value: String(root.stats.isolatedNodes || 0)
                delta: ""
                subtext: "Entities without persisted links"
                iconSource: "../../assets/icons/graph.svg"
                accentColor: Theme.warning
                chartType: "none"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.panelGap

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Graph Explorer"
                subtitle: root.graph.notice || "Select a focus entity and inspect one or two relationship hops"
                iconSource: "../../assets/icons/graph_blue.svg"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        spacing: 8

                        Text {
                            text: "FOCUS"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.Medium
                            font.letterSpacing: 1.0
                        }
                        AppComboBox {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            enabled: root.options.length > 0
                            model: root.optionLabels()
                            currentIndex: root.focusIndex()
                            onActivated: function(index) {
                                if (index >= 0 && index < root.options.length)
                                    desktopBridge.selectGraphEntity(String(root.options[index].id || ""))
                            }
                        }
                        Text {
                            text: "DEPTH"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.Medium
                            font.letterSpacing: 1.0
                        }
                        AppComboBox {
                            Layout.preferredWidth: 102
                            Layout.preferredHeight: 34
                            model: ["1 hop", "2 hops"]
                            currentIndex: Number(root.graph.depth || 1) >= 2 ? 1 : 0
                            onActivated: function(index) { desktopBridge.setGraphDepth(index + 1) }
                        }
                        AppButton {
                            Layout.preferredWidth: 94
                            Layout.preferredHeight: 34
                            text: "Reset view"
                            onClicked: graphWeb.resetView()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 9
                        color: "#091a28"
                        border.width: 1
                        border.color: Theme.border
                        clip: true

                        EntityWeb {
                            id: graphWeb
                            anchors.fill: parent
                            anchors.margins: 8
                            nodes: root.graph.nodes || []
                            edges: root.graph.edges || []
                            showEdgeLabels: Boolean(desktopBridge.uiSettings.graphEdgeLabels)
                            showTypeLabels: true
                            emptyText: root.graph.notice || "No graph data"
                            onNodeClicked: function(entityId) { desktopBridge.selectGraphEntity(entityId) }
                            onNodeDoubleClicked: function(entityId) { desktopBridge.openGraphEntity(entityId) }
                        }
                    }
                }
            }

            Panel {
                Layout.preferredWidth: 322
                Layout.maximumWidth: 350
                Layout.fillHeight: true
                title: "Graph Context"
                subtitle: "Current focus and relationship mix"
                iconSource: "../../assets/icons/graph.svg"

                Flickable {
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: contextColumn.height
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: contextColumn
                        width: parent.width
                        spacing: 0

                        Rectangle {
                            width: parent.width
                            height: 92
                            color: "transparent"
                            Text { x: 16; y: 13; text: "SELECTED ENTITY"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                            Text { x: 16; y: 34; width: parent.width - 32; text: String(root.graph.focusLabel || "None"); color: Theme.textPrimary; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight }
                            Text { x: 16; y: 58; width: parent.width - 32; text: String(root.graph.focusType || "Select an entity"); color: Theme.accent; font.pixelSize: 10; elide: Text.ElideRight }
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        }

                        Rectangle {
                            width: parent.width
                            height: 86
                            color: "transparent"
                            Text { x: 16; y: 13; text: "VISIBLE SUBGRAPH"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                            Text { x: 16; y: 35; text: String(root.stats.visibleNodes || 0) + " nodes"; color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.Medium }
                            Text { x: 16; y: 57; text: String(root.stats.visibleEdges || 0) + " relationships"; color: Theme.textSecondary; font.pixelSize: 10 }
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        }

                        Text {
                            x: 16
                            topPadding: 14
                            bottomPadding: 8
                            text: "RELATIONSHIP TYPES"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.letterSpacing: 1.0
                        }

                        Repeater {
                            model: root.relationshipTypes
                            delegate: Rectangle {
                                id: relationTypeRow
                                required property var modelData
                                width: contextColumn.width
                                height: 46
                                color: "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 16; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 74; text: String(relationTypeRow.modelData.label || "Related"); color: Theme.textSecondary; font.pixelSize: 10; elide: Text.ElideRight }
                                Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: String(relationTypeRow.modelData.count || 0); color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.DemiBold }
                            }
                        }

                        Text {
                            width: parent.width - 32
                            x: 16
                            topPadding: 18
                            bottomPadding: 18
                            text: root.graph.notice || "Double-click a PERSON node to open its identity card. Mouse wheel zooms; middle/right drag pans."
                            color: Theme.textMuted
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }
        }
    }
}
