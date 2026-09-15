pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property real pad: width < 1200 ? 16 : Spacing.page
    property real gap: Spacing.panelGap
    property var dashboardData: desktopBridge.dashboard
    property var graphNodes: dashboardData.graphNodes || []
    property var graphEdges: dashboardData.graphEdges || []
    property var graphOptions: dashboardData.graphOptions || []
    property var personSummary: dashboardData.personSummary || []

    function reload() {
        root.dashboardData = desktopBridge.dashboard
        root.graphNodes = root.dashboardData.graphNodes || []
        root.graphEdges = root.dashboardData.graphEdges || []
        root.graphOptions = root.dashboardData.graphOptions || []
        root.personSummary = root.dashboardData.personSummary || []
    }

    function personLabels() {
        var result = []
        for (var i = 0; i < root.graphOptions.length; ++i)
            result.push(String(root.graphOptions[i].label || "Unnamed person"))
        return result
    }

    function focusIndex() {
        var focus = String(root.dashboardData.graphFocusId || "")
        for (var i = 0; i < root.graphOptions.length; ++i) {
            if (String(root.graphOptions[i].id || "") === focus) return i
        }
        return root.graphOptions.length > 0 ? 0 : -1
    }

    function focusAvatar() {
        if (root.graphNodes.length > 0)
            return String(root.graphNodes[0].avatarUrl || "")
        return ""
    }

    function openCase(caseId) {
        if (!caseId) return
        desktopBridge.openCase(caseId)
        desktopBridge.navigateTo("cases")
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.reload() }
    }

    opacity: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.pad
        anchors.rightMargin: root.pad
        anchors.topMargin: 12
        anchors.bottomMargin: 24
        spacing: root.gap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 104

            Text {
                x: 2
                y: 1
                text: root.dashboardData.dateLabel || ""
                color: "#8097aa"
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.8
            }
            Text {
                x: 2
                y: 23
                text: root.dashboardData.greeting || "Welcome."
                color: Theme.textPrimary
                font.pixelSize: Typography.pageTitle
                font.weight: Font.DemiBold
            }
            Text {
                x: 3
                y: 65
                text: root.dashboardData.summary || ""
                color: Theme.textSecondary
                font.pixelSize: 14
            }

            Column {
                visible: Boolean(desktopBridge.uiSettings.showSlogan)
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.top: parent.top
                anchors.topMargin: 12
                width: Math.min(340, parent.width * 0.30)
                spacing: 4
                Text {
                    width: parent.width
                    text: "\"Information creates advantage.\""
                    color: "#91a9be"
                    font.pixelSize: 12
                    font.italic: true
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: "— OSINTXZ"
                    color: Theme.accent
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.2
                    horizontalAlignment: Text.AlignRight
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 122
            spacing: root.gap

            StatCard {
                Layout.fillWidth: true
                title: "Active Cases"
                value: String(root.dashboardData.activeCases || 0)
                delta: ""
                subtext: root.dashboardData.activeCases ? "Open investigations" : "No active investigations"
                iconSource: "../../assets/icons/folder_blue.svg"
                accentColor: Theme.accent
                chartType: "none"
                clickable: true
                onClicked: desktopBridge.navigateTo("cases")
            }
            StatCard {
                Layout.fillWidth: true
                title: "Entities"
                value: String(root.dashboardData.entities || 0)
                delta: ""
                subtext: "People, organizations and identifiers"
                iconSource: "../../assets/icons/users_cyan.svg"
                accentColor: Theme.cyan
                chartType: "none"
                clickable: true
                onClicked: desktopBridge.navigateTo("entities")
            }
            StatCard {
                Layout.fillWidth: true
                title: "Findings"
                value: String(root.dashboardData.findings || 0)
                delta: ""
                subtext: "Persisted evidence items"
                iconSource: "../../assets/icons/document.svg"
                accentColor: "#6d8ee8"
                chartType: "none"
                clickable: true
                onClicked: desktopBridge.navigateTo("evidence")
            }
            StatCard {
                Layout.fillWidth: true
                title: "Risks"
                value: String(root.dashboardData.risks || 0)
                delta: ""
                subtext: "Risk model not implemented yet"
                iconSource: "../../assets/icons/warning_red.svg"
                accentColor: Theme.danger
                negative: true
                chartType: "none"
                clickable: false
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: root.gap

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 286
                Layout.minimumWidth: 250
                Layout.maximumWidth: 320
                title: "Selected Person"
                subtitle: "One identity at a time"
                iconSource: "../../assets/icons/users_cyan.svg"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    AppComboBox {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        enabled: root.graphOptions.length > 0
                        model: root.personLabels()
                        currentIndex: root.focusIndex()
                        onActivated: function(index) {
                            if (index >= 0 && index < root.graphOptions.length)
                                desktopBridge.selectDashboardEntity(String(root.graphOptions[index].id || ""))
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 158

                        CircularAvatar {
                            id: selectedPersonAvatar
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            width: 82
                            height: 82
                            source: root.focusAvatar()
                            fallbackSource: "../../assets/icons/users_purple.svg"
                            backgroundColor: "#152a42"
                            borderColor: Theme.accent
                            borderWidth: 2
                            inset: source.toString().length > 0 ? 2 : 0
                        }

                        Text {
                            id: selectedPersonName
                            anchors.top: selectedPersonAvatar.bottom
                            anchors.topMargin: 8
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width
                            text: String(root.dashboardData.graphPersonTitle || "Select a person")
                            color: Theme.textPrimary
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            anchors.top: selectedPersonName.bottom
                            anchors.topMargin: 6
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: personTypeLabel.implicitWidth + 16
                            height: 22
                            radius: 11
                            color: "#221b3a"
                            border.width: 1
                            border.color: "#8d6ccf"
                            visible: String(root.dashboardData.graphFocusId || "").length > 0

                            Text {
                                id: personTypeLabel
                                anchors.centerIn: parent
                                text: "PERSON"
                                color: "#bda6ff"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.6
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: root.personSummary
                        clip: true
                        spacing: 1
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Item {
                            id: summaryRow
                            required property var modelData
                            width: ListView.view.width
                            height: 48

                            Text {
                                x: 1; y: 4
                                width: parent.width - 2
                                text: String(summaryRow.modelData.label || "Data")
                                color: Theme.textMuted
                                font.pixelSize: 8
                                font.letterSpacing: 0.5
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 1; y: 22
                                width: parent.width - 2
                                text: String(summaryRow.modelData.value || "")
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.personSummary.length === 0
                        text: desktopBridge.currentCaseId
                            ? "Add or select intelligence on the person card."
                            : "Select a case first."
                        color: Theme.textMuted
                        font.pixelSize: 9
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }

                    AppButton {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        text: "Open Person"
                        enabled: String(root.dashboardData.graphFocusId || "").length > 0
                        onClicked: desktopBridge.openDashboardFocus()
                    }
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 610
                title: "Linked Profiles & Accounts"
                subtitle: "Only usernames and accounts explicitly associated with the selected person"
                iconSource: "../../assets/icons/graph_blue.svg"

                Item {
                    anchors.fill: parent

                    EntityWeb {
                        id: profileWeb
                        anchors.fill: parent
                        anchors.margins: 10
                        nodes: root.graphNodes
                        edges: root.graphEdges
                        showEdgeLabels: false
                        showTypeLabels: false
                        emptyText: desktopBridge.currentCaseTitle
                            ? (String(root.dashboardData.graphNotice || "") || "No linked accounts yet")
                            : "Select an investigation from Cases"
                        onNodeDoubleClicked: function(entityId) {
                            if (String(entityId || "") === String(root.dashboardData.graphFocusId || ""))
                                desktopBridge.openDashboardFocus()
                        }
                    }

                    Row {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.rightMargin: 12
                        anchors.topMargin: 10
                        spacing: 8

                        AppButton {
                            width: 102
                            height: 30
                            text: "Full Graph"
                            enabled: Boolean(desktopBridge.currentCaseId)
                            onClicked: desktopBridge.navigateTo("graph")
                        }
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        anchors.bottomMargin: 8
                        text: root.graphNodes.length > 1
                            ? String(root.dashboardData.graphAccountCount || 0) + " linked username/account node(s)"
                            : "Use From intelligence on the person card to link existing OSINT results."
                        color: Theme.textMuted
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }
                }
            }

            ColumnLayout {
                Layout.fillHeight: true
                Layout.preferredWidth: 410
                Layout.minimumWidth: 340
                Layout.maximumWidth: 460
                spacing: root.gap

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 300
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
                                clickable: true
                                onClicked: desktopBridge.navigateTo(String(modelData.page || "evidence"))
                            }
                        }
                        Text {
                            visible: (root.dashboardData.recentIntelligence || []).length === 0
                            width: parent.width
                            height: 100
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                            text: "No recent intelligence"
                            color: Theme.textMuted
                            font.pixelSize: 12
                        }
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
                                name: String(modelData.title || "Untitled investigation")
                                detail: String(modelData.detail || "No description")
                                priority: String(modelData.status || "Active")
                                priorityColor: modelData.color || Theme.accent
                                timeText: String(modelData.meta || "")
                                caseId: String(modelData.id || "")
                                clickable: true
                                onClicked: root.openCase(caseId)
                            }
                        }
                    }
                }
            }
        }
    }
}
