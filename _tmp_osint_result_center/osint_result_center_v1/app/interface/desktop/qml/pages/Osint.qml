pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property string activeTab: "findings"
    property var runData: desktopBridge.osintRun || ({})
    property var summary: runData.summary || ({})
    property bool hasRun: Boolean(runData.hasRun)

    function runStatusLabel() {
        const status = String(root.runData.status || "")
        if (status === "completed") return "Completed"
        if (status === "completed_with_errors") return "Completed with warnings"
        if (status === "failed") return "Failed"
        return status.length > 0 ? status.replace(/_/g, " ") : "No run"
    }

    function runStatusShort() {
        const status = String(root.runData.status || "")
        if (status === "completed") return "Complete"
        if (status === "completed_with_errors") return "Warnings"
        if (status === "failed") return "Failed"
        return "—"
    }

    function runStatusColor() {
        const status = String(root.runData.status || "")
        if (status === "completed") return Theme.success
        if (status === "completed_with_errors") return Theme.warning
        if (status === "failed") return Theme.danger
        return Theme.textMuted
    }

    function runStatusTint() {
        const status = String(root.runData.status || "")
        if (status === "completed") return "#12362f"
        if (status === "completed_with_errors") return "#3b3015"
        if (status === "failed") return "#3a1e26"
        return "#1a2b37"
    }

    function tabCount(tabName) {
        if (!root.hasRun) return 0
        if (tabName === "findings") return Number(root.summary.findings || 0)
        if (tabName === "entities") return (root.runData.entities || []).length
        if (tabName === "evidence") return (root.runData.evidence || []).length
        if (tabName === "leads") return Number(root.summary.leads || 0)
        if (tabName === "errors") return Number(root.summary.errors || 0)
        if (tabName === "connectors") return Number(root.summary.connectors || 0)
        return 0
    }

    function itemsForTab() {
        if (!root.hasRun) return []
        if (root.activeTab === "findings") return root.runData.findings || []
        if (root.activeTab === "entities") return root.runData.entities || []
        if (root.activeTab === "evidence") return root.runData.evidence || []
        if (root.activeTab === "leads") return root.runData.leads || []
        if (root.activeTab === "errors") return root.runData.errors || []
        if (root.activeTab === "connectors") return root.runData.connectors || []
        return []
    }

    function emptyTitleForTab() {
        if (root.activeTab === "findings") return "No confirmed findings"
        if (root.activeTab === "entities") return "No linked entities"
        if (root.activeTab === "evidence") return "No persisted evidence"
        if (root.activeTab === "leads") return "No discovery leads"
        if (root.activeTab === "errors") return "No collection errors"
        return "No connector activity"
    }

    function emptyDescriptionForTab() {
        if (root.activeTab === "errors") return "The last collection completed without connector errors."
        if (root.activeTab === "entities") return "No entity candidates from this run were linked into the investigation."
        if (root.activeTab === "evidence") return "No evidence items from this run were persisted into the investigation."
        return "The last collection did not return items for this view."
    }

    function rowDetail(row) {
        if (root.activeTab === "connectors") {
            const error = String(row.error || "").trim()
            if (error.length > 0) return error
            const goal = String(row.goal || "").replace(/_/g, " ")
            return goal.length > 0 ? goal : "OSINT connector"
        }
        return String(row.detail || "")
    }

    function rowStatus(row) {
        if (root.activeTab === "connectors")
            return String(row.statusLabel || row.status || "Connector")
        return String(row.status || "Result")
    }

    function rowMeta(row) {
        if (root.activeTab === "connectors") {
            return "F " + Number(row.findingCount || 0)
                    + "  ·  L " + Number(row.leadCount || 0)
                    + "  ·  " + String(row.meta || "")
        }
        return String(row.meta || "")
    }

    function detailValue(key, fallback) {
        const value = root.runData[key]
        if (value === undefined || value === null || String(value).length === 0)
            return fallback || "—"
        return String(value)
    }

    opacity: 0
    Component.onCompleted: appear.start()
    NumberAnimation {
        id: appear
        target: root
        property: "opacity"
        from: 0
        to: 1
        duration: Motion.page
        easing.type: Easing.OutCubic
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 18
        anchors.bottomMargin: 26
        spacing: Spacing.panelGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 75

            Text {
                x: 1
                y: 0
                text: "SOURCE OPERATIONS"
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }

            Text {
                x: 1
                y: 20
                text: "OSINT"
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }

            Text {
                x: 2
                y: 57
                text: "Run external intelligence collections and inspect exactly what each run discovered."
                color: Theme.textSecondary
                font.pixelSize: 13
            }

            AppButton {
                id: runButton
                objectName: "primaryActionButton"
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 154
                height: 38
                text: "+   Run Collection"
                primary: true
                enabled: desktopBridge.hasCurrentCase
                ToolTip.visible: hovered && !enabled
                ToolTip.delay: 450
                ToolTip.text: "Select an investigation before running OSINT collection."
                onClicked: collectionDialog.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 112
            spacing: Spacing.panelGap

            StatCard {
                Layout.fillWidth: true
                title: "Connectors"
                value: String(desktopBridge.osintConnectorCount)
                delta: ""
                subtext: "Registered in the current pipeline"
                iconSource: "../../assets/icons/globe_blue.svg"
                accentColor: Theme.accent
                chartType: "none"
            }

            StatCard {
                Layout.fillWidth: true
                title: "Last Run"
                value: root.hasRun ? root.runStatusShort() : "—"
                delta: ""
                subtext: root.hasRun
                    ? (String(root.runData.targetType || "Target").toUpperCase()
                       + " · " + String(root.runData.targetValue || ""))
                    : "No collection in this session"
                iconSource: "../../assets/icons/chart.svg"
                accentColor: root.runStatusColor()
                chartType: "none"
            }

            StatCard {
                Layout.fillWidth: true
                title: "Findings"
                value: root.hasRun ? String(root.summary.findings || 0) : "0"
                delta: ""
                subtext: root.hasRun
                    ? (String(root.summary.evidenceCreated || 0) + " new evidence · "
                       + String(root.summary.entitiesCreated || 0) + " new entities")
                    : "Confirmed/extracted results from last run"
                iconSource: "../../assets/icons/document_blue.svg"
                accentColor: Theme.success
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
                Layout.preferredWidth: 850
                title: "Collection Results"
                subtitle: root.hasRun
                    ? (String(root.runData.targetType || "target").replace(/_/g, " ").toUpperCase()
                       + " · " + String(root.runData.targetValue || ""))
                    : "Results from the latest collection appear here"
                iconSource: "../../assets/icons/globe_blue.svg"

                Item {
                    anchors.fill: parent

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: !root.hasRun
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "No collection results yet"
                        description: desktopBridge.hasCurrentCase
                            ? "Run an OSINT collection to discover and persist intelligence for the selected investigation."
                            : "Select an investigation first, then run an OSINT collection."
                    }

                    Item {
                        anchors.fill: parent
                        visible: root.hasRun

                        Item {
                            id: runSummaryStrip
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            height: 70

                            Text {
                                x: 18
                                y: 12
                                width: parent.width - 260
                                text: String(root.runData.targetValue || "Unknown target")
                                color: Theme.textPrimary
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 18
                                y: 39
                                width: parent.width - 260
                                text: String(root.summary.connectors || 0) + " connectors"
                                      + "  ·  " + String(root.summary.findings || 0) + " findings"
                                      + "  ·  " + String(root.summary.leads || 0) + " leads"
                                      + "  ·  " + String(root.summary.errors || 0) + " errors"
                                color: Theme.textMuted
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }

                            Rectangle {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(96, statusText.implicitWidth + 24)
                                height: 28
                                radius: 7
                                color: root.runStatusTint()
                                border.color: root.runStatusColor()

                                Text {
                                    id: statusText
                                    anchors.centerIn: parent
                                    text: root.runStatusLabel()
                                    color: root.runStatusColor()
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                }
                            }

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }
                        }

                        Item {
                            id: tabsBar
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: runSummaryStrip.bottom
                            height: 46

                            Row {
                                anchors.left: parent.left
                                anchors.leftMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 6

                                Repeater {
                                    model: [
                                        { key: "findings", label: "Findings" },
                                        { key: "entities", label: "Entities" },
                                        { key: "evidence", label: "Evidence" },
                                        { key: "leads", label: "Leads" },
                                        { key: "errors", label: "Errors" },
                                        { key: "connectors", label: "Connectors" }
                                    ]

                                    delegate: Rectangle {
                                        id: tabButton
                                        required property var modelData
                                        property bool selected: root.activeTab === String(modelData.key)
                                        width: tabLabel.implicitWidth + 24
                                        height: 28
                                        radius: 6
                                        color: selected
                                            ? Theme.accentSoft
                                            : (tabMouse.containsMouse ? Theme.surfaceHover : "transparent")
                                        border.color: selected ? Theme.accent : "transparent"
                                        Behavior on color { ColorAnimation { duration: Motion.hover } }

                                        Text {
                                            id: tabLabel
                                            anchors.centerIn: parent
                                            text: String(tabButton.modelData.label)
                                                  + "  " + root.tabCount(String(tabButton.modelData.key))
                                            color: tabButton.selected ? Theme.textPrimary : Theme.textSecondary
                                            font.pixelSize: 10
                                            font.weight: tabButton.selected ? Font.Medium : Font.Normal
                                        }

                                        MouseArea {
                                            id: tabMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.activeTab = String(tabButton.modelData.key)
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }
                        }

                        ListView {
                            id: resultsView
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: tabsBar.bottom
                            anchors.bottom: parent.bottom
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            cacheBuffer: 320
                            reuseItems: true
                            model: root.itemsForTab()

                            delegate: Rectangle {
                                id: resultRow
                                required property var modelData
                                width: resultsView.width
                                height: 70
                                color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"
                                Behavior on color { ColorAnimation { duration: Motion.hover } }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }

                                Rectangle {
                                    x: 18
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 36
                                    radius: 4
                                    color: resultRow.modelData.color || Theme.accent
                                }

                                Text {
                                    x: 40
                                    y: 13
                                    width: Math.max(100, parent.width - 300)
                                    text: String(resultRow.modelData.title || "OSINT result")
                                    color: Theme.textPrimary
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                }

                                Text {
                                    x: 40
                                    y: 38
                                    width: Math.max(100, parent.width - 300)
                                    text: root.rowDetail(resultRow.modelData)
                                    color: Theme.textMuted
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                }

                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 18
                                    y: 10
                                    width: Math.min(174, Math.max(74, rowBadgeText.implicitWidth + 22))
                                    height: 24
                                    radius: 6
                                    color: resultRow.modelData.tint || "#142b47"
                                    border.color: resultRow.modelData.color || Theme.accent

                                    Text {
                                        id: rowBadgeText
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        text: root.rowStatus(resultRow.modelData)
                                        color: resultRow.modelData.color || Theme.accent
                                        font.pixelSize: 9
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        elide: Text.ElideRight
                                    }
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 18
                                    y: 42
                                    width: 190
                                    text: root.rowMeta(resultRow.modelData)
                                    color: Theme.textMuted
                                    font.pixelSize: 9
                                    horizontalAlignment: Text.AlignRight
                                    elide: Text.ElideRight
                                }

                                MouseArea {
                                    id: rowMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
                            }

                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }

                        EmptyState {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: tabsBar.bottom
                            anchors.bottom: parent.bottom
                            anchors.margins: 18
                            visible: resultsView.count === 0
                            iconSource: "../../assets/icons/document_blue.svg"
                            title: root.emptyTitleForTab()
                            description: root.emptyDescriptionForTab()
                        }
                    }
                }
            }

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 400
                Layout.maximumWidth: 440
                title: "Run Details"
                subtitle: root.hasRun ? root.runStatusLabel() : "Current investigation context"
                iconSource: "../../assets/icons/chart.svg"

                Item {
                    anchors.fill: parent

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: !root.hasRun
                        iconSource: "../../assets/icons/chart.svg"
                        title: desktopBridge.hasCurrentCase
                            ? "Ready to collect"
                            : "No investigation selected"
                        description: desktopBridge.hasCurrentCase
                            ? ("Collection results will be attached to " + desktopBridge.currentCaseTitle + ".")
                            : "Open an investigation to keep findings, evidence and entities in one case."
                    }

                    Flickable {
                        id: detailsFlick
                        anchors.fill: parent
                        visible: root.hasRun
                        clip: true
                        contentWidth: width
                        contentHeight: detailsColumn.height
                        boundsBehavior: Flickable.StopAtBounds

                        Column {
                            id: detailsColumn
                            width: detailsFlick.width

                            Repeater {
                                model: [
                                    { label: "INVESTIGATION", value: root.detailValue("caseTitle", "Unknown investigation") },
                                    { label: "TARGET", value: root.detailValue("targetValue", "—") },
                                    { label: "TYPE", value: root.detailValue("targetType", "—").replace(/_/g, " ").toUpperCase() },
                                    { label: "STARTED", value: root.detailValue("startedLabel", "—") },
                                    { label: "DURATION", value: root.detailValue("durationText", "—") },
                                    { label: "CONNECTORS", value: String(root.summary.connectors || 0) },
                                    { label: "SUCCEEDED / PARTIAL", value: String(root.summary.successful || 0) + " / " + String(root.summary.partial || 0) },
                                    { label: "PERSISTED FINDINGS", value: String(root.summary.persistedFindings || 0) },
                                    { label: "EVIDENCE CREATED", value: String(root.summary.evidenceCreated || 0) },
                                    { label: "ENTITIES CREATED", value: String(root.summary.entitiesCreated || 0) },
                                    { label: "EVIDENCE LINKS", value: String(root.summary.linksCreated || 0) }
                                ]

                                delegate: Rectangle {
                                    id: detailRow
                                    required property var modelData
                                    width: detailsColumn.width
                                    height: 55
                                    color: "transparent"

                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        height: 1
                                        color: Theme.divider
                                    }

                                    Text {
                                        x: 18
                                        y: 10
                                        width: parent.width - 36
                                        text: String(detailRow.modelData.label)
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        font.weight: Font.Medium
                                        font.letterSpacing: 1.1
                                    }

                                    Text {
                                        x: 18
                                        y: 28
                                        width: parent.width - 36
                                        text: String(detailRow.modelData.value)
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                        maximumLineCount: 1
                                    }
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }
        }
    }

    AppDialog {
        id: collectionDialog
        objectName: "runCollectionDialog"
        width: 470
        title: "Run OSINT collection"
        description: "Collect external intelligence and persist supported findings into the selected investigation."
        primaryText: "Run Collection"
        bodyHeight: 232

        onAccepted: {
            if (!desktopBridge.hasCurrentCase) {
                open()
                return
            }

            const target = targetInput.text.trim()
            if (target.length === 0) {
                open()
                targetInput.forceActiveFocus()
                return
            }

            root.activeTab = "findings"
            const ok = desktopBridge.runOsint(typeBox.currentText, target)
            if (ok) {
                targetInput.clear()
            } else if (!desktopBridge.osintRun.hasRun) {
                open()
                targetInput.forceActiveFocus()
            }
        }

        Column {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 16
            anchors.bottomMargin: 14
            spacing: 6

            Text {
                text: "TARGET TYPE"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.2
            }

            AppComboBox {
                id: typeBox
                objectName: "collectionTargetType"
                width: parent.width
                model: ["Email", "Username", "Domain", "IP", "URL", "Phone"]
            }

            Item { width: 1; height: 3 }

            Text {
                text: "COLLECTION TARGET"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.2
            }

            AppTextField {
                id: targetInput
                objectName: "collectionTargetInput"
                width: parent.width
                placeholderText: "Collection target"
                Keys.onReturnPressed: collectionDialog.accept()
            }

            Text {
                width: parent.width
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: 10
                text: desktopBridge.hasCurrentCase
                    ? ("Results will be stored in “" + desktopBridge.currentCaseTitle + "”.")
                    : "Select an investigation before running collection."
            }

            Text {
                visible: desktopBridge.message.length > 0
                width: parent.width
                wrapMode: Text.Wrap
                color: Theme.textSecondary
                font.pixelSize: 10
                text: desktopBridge.message
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }

        onOpened: targetInput.forceActiveFocus()
    }
}
