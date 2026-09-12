pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root
    property real pad: width < 1200 ? 16 : Spacing.page
    property real gap: Spacing.panelGap
    property var dashboardData: desktopBridge.dashboard

    function reload() {
        root.dashboardData = desktopBridge.dashboard
        graphCanvas.requestPaint()
    }

    function nodeX(index, count, width) {
        if (count <= 1) return width * 0.50
        return width * 0.50 + Math.cos(-Math.PI / 2 + index * Math.PI * 2 / count) * width * 0.34
    }

    function nodeY(index, count, height) {
        if (count <= 1) return height * 0.47
        return height * 0.48 + Math.sin(-Math.PI / 2 + index * Math.PI * 2 / count) * height * 0.34
    }

    function nodeIcon(type) {
        var key = String(type || "").toLowerCase()
        if (key === "person") return "../../assets/icons/users_purple.svg"
        if (key === "organization") return "../../assets/icons/building_cyan.svg"
        if (key === "email") return "../../assets/icons/mail_blue.svg"
        if (key === "phone") return "../../assets/icons/phone_green.svg"
        if (key === "location" || key === "address") return "../../assets/icons/pin_purple.svg"
        if (key === "domain" || key === "url" || key === "ip") return "../../assets/icons/globe_blue.svg"
        return "../../assets/icons/document.svg"
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.reload() }
    }

    opacity: 0
    Component.onCompleted: appear.start()
    NumberAnimation { id: appear; target: root; property: "opacity"; from: 0; to: 1; duration: Motion.page; easing.type: Easing.OutCubic }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.pad
        anchors.rightMargin: root.pad
        anchors.topMargin: 13
        anchors.bottomMargin: 26
        spacing: root.gap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 92
            Text { x: 2; y: 2; text: root.dashboardData.dateLabel || ""; color: "#8097aa"; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 1.8 }
            Text { x: 2; y: 21; text: root.dashboardData.greeting || "Welcome."; color: Theme.textPrimary; font.pixelSize: Typography.pageTitle; font.weight: Font.DemiBold }
            Text { x: 3; y: 61; text: root.dashboardData.summary || ""; color: Theme.textSecondary; font.pixelSize: 14 }
            Image { anchors.right: parent.right; anchors.top: parent.top; width: Math.min(470, parent.width * 0.38); height: 92; source: "../../assets/images/world_map_dots.svg"; fillMode: Image.PreserveAspectFit; opacity: 0.35 }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 122
            spacing: root.gap
            StatCard { Layout.fillWidth: true; title: "Active Cases"; value: String(root.dashboardData.activeCases || 0); delta: ""; subtext: root.dashboardData.activeCases ? "Stored active investigations" : "No active investigations"; iconSource: "../../assets/icons/folder_blue.svg"; accentColor: Theme.accent; chartType: "none" }
            StatCard { Layout.fillWidth: true; title: "Entities"; value: String(root.dashboardData.entities || 0); delta: ""; subtext: "Stored across investigations"; iconSource: "../../assets/icons/users_cyan.svg"; accentColor: Theme.cyan; chartType: "none" }
            StatCard { Layout.fillWidth: true; title: "Findings"; value: String(root.dashboardData.findings || 0); delta: ""; subtext: "Persisted evidence items"; iconSource: "../../assets/icons/document.svg"; accentColor: "#6d8ee8"; chartType: "none" }
            StatCard { Layout.fillWidth: true; title: "Risks"; value: String(root.dashboardData.risks || 0); delta: ""; subtext: "No persisted risk metric"; iconSource: "../../assets/icons/warning_red.svg"; accentColor: Theme.danger; negative: true; chartType: "none" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: root.gap

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 820
                title: root.dashboardData.graphCaseTitle ? "Investigation Graph · " + root.dashboardData.graphCaseTitle : "Investigation Graph"
                subtitle: root.dashboardData.graphCaseTitle ? "Entity relationships from the selected investigation" : "Open a case to load its entity relationships"
                iconSource: "../../assets/icons/graph_blue.svg"
                headerHeight: 74
                headerDivider: false

                Item {
                    id: graphArea
                    anchors.fill: parent
                    Item {
                        id: networkLayer
                        anchors.centerIn: parent
                        width: Math.min(parent.width, 1050)
                        height: Math.min(parent.height, 640)

                        Canvas {
                            anchors.fill: parent
                            opacity: 0.09
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                ctx.fillStyle = "#31516b"
                                for (var py = 4; py < height; py += 15)
                                    for (var px = 6; px < width; px += 15) ctx.fillRect(px, py, 1, 1)
                            }
                        }

                        Canvas {
                            id: graphCanvas
                            anchors.fill: parent
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                var nodes = root.dashboardData.graphNodes || []
                                var edges = root.dashboardData.graphEdges || []
                                var indexes = {}
                                for (var i = 0; i < nodes.length; ++i) indexes[String(nodes[i].id)] = i
                                ctx.strokeStyle = "#7892aa"
                                ctx.lineWidth = 1.1
                                ctx.globalAlpha = 0.75
                                for (var e = 0; e < edges.length; ++e) {
                                    var a = indexes[String(edges[e].source)]
                                    var b = indexes[String(edges[e].target)]
                                    if (a === undefined || b === undefined) continue
                                    ctx.beginPath()
                                    ctx.moveTo(root.nodeX(a, nodes.length, width), root.nodeY(a, nodes.length, height))
                                    ctx.lineTo(root.nodeX(b, nodes.length, width), root.nodeY(b, nodes.length, height))
                                    ctx.stroke()
                                }
                            }
                            onWidthChanged: requestPaint()
                            onHeightChanged: requestPaint()
                        }

                        Repeater {
                            model: root.dashboardData.graphNodes || []
                            delegate: EntityNode {
                                required property var modelData
                                required property int index
                                central: (root.dashboardData.graphNodes || []).length === 1
                                nodeX: root.nodeX(index, (root.dashboardData.graphNodes || []).length, networkLayer.width)
                                nodeY: root.nodeY(index, (root.dashboardData.graphNodes || []).length, networkLayer.height)
                                title: String(modelData.label || "Unnamed entity")
                                subtitle: String(modelData.type || "Entity").replace("_", " ")
                                labelSide: index < 3 ? "right" : "left"
                                iconSource: root.nodeIcon(modelData.type)
                                nodeColor: index === 0 ? Theme.accent : Theme.purple
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: (root.dashboardData.graphNodes || []).length === 0
                            text: desktopBridge.currentCaseTitle ? "No entities in this investigation" : "Select an investigation from Cases"
                            color: Theme.textMuted
                            font.pixelSize: 13
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillHeight: true
                Layout.preferredWidth: 480
                Layout.maximumWidth: 520
                spacing: root.gap

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 322
                    title: "Recent Intelligence"
                    iconSource: "../../assets/icons/document_blue.svg"
                    Column {
                        anchors.fill: parent
                        Repeater {
                            model: root.dashboardData.recentIntelligence || []
                            delegate: RecentRow {
                                required property var modelData
                                iconSource: "../../assets/icons/" + modelData.icon
                                iconColor: modelData.color
                                headline: modelData.headline
                                detail: modelData.detail
                                timeText: modelData.timeText
                            }
                        }
                        Text { visible: (root.dashboardData.recentIntelligence || []).length === 0; width: parent.width; height: 100; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter; text: "No recent intelligence"; color: Theme.textMuted; font.pixelSize: 12 }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: "Recent Cases"
                    iconSource: "../../assets/icons/folder_blue.svg"
                    Column {
                        anchors.fill: parent
                        Repeater {
                            model: root.dashboardData.recentCases || []
                            delegate: CaseRow {
                                required property var modelData
                                name: modelData.title
                                detail: modelData.detail
                                priority: modelData.status
                                priorityColor: modelData.color
                                timeText: modelData.meta
                            }
                        }
                        Text { visible: (root.dashboardData.recentCases || []).length === 0; width: parent.width; height: 100; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter; text: "No active investigations"; color: Theme.textMuted; font.pixelSize: 12 }
                    }
                }
            }
        }
    }
}
