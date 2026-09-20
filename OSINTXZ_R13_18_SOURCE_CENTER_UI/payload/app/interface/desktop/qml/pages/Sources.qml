pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var center: sourceBridge.sourceCenter || ({})
    property var counts: center.counts || ({})
    property var allSources: center.sources || []
    property var runData: sourceBridge.runData || ({})
    property var runSummary: runData.summary || ({})
    property int selectedIndex: -1
    property string filterText: ""
    property string subsystemFilter: "All"
    property string resultTab: "records"

    property var selectedSource: selectedIndex >= 0 && selectedIndex < filteredSources().length
        ? filteredSources()[selectedIndex] : ({})

    function pretty(value) {
        return String(value || "").replace(/_/g, " ").replace(/\b\w/g, function(c) { return c.toUpperCase() })
    }

    function filteredSources() {
        const q = filterText.trim().toLowerCase()
        const subsystem = subsystemFilter
        return allSources.filter(function(item) {
            if (subsystem !== "All" && String(item.subsystem || "") !== subsystem) return false
            if (q.length === 0) return true
            const haystack = [item.title, item.code, item.subsystem, item.capabilitiesText, item.categoryText, item.countriesText]
                .join(" ").toLowerCase()
            return haystack.indexOf(q) >= 0
        })
    }

    function statusColor(row) {
        if (Boolean(row.configured)) return Theme.success
        if (String(row.implementationStatus || "") === "cataloged") return Theme.textMuted
        if (String(row.implementationStatus || "") === "manual_assisted") return Theme.warning
        return Theme.danger
    }

    function runStatusColor() {
        const status = String(runData.status || "")
        if (status === "running") return Theme.accent
        if (status === "completed") return Theme.success
        if (status === "completed_with_errors") return Theme.warning
        if (status === "failed") return Theme.danger
        return Theme.textMuted
    }

    function sourceActionLabel(row) {
        if (Boolean(row.searchable)) return "Double-click to search"
        if (String(row.routePage || "") === "registry") return "Open Registry"
        if (String(row.routePage || "") === "osint") return "Open OSINT"
        return "Catalog only"
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
                x: 1; y: 0
                text: "INTELLIGENCE FEDERATION"
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 1; y: 20
                text: "Sources"
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Text {
                x: 2; y: 57
                text: "Inspect every configured source and run bounded remote searches without downloading bulk datasets."
                color: Theme.textSecondary
                font.pixelSize: 13
            }

            AppButton {
                anchors.right: searchButton.left
                anchors.rightMargin: 10
                anchors.bottom: parent.bottom
                width: 126; height: 38
                text: "Refresh"
                enabled: !sourceBridge.busy
                onClicked: sourceBridge.refresh()
            }
            AppButton {
                id: searchButton
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 176; height: 38
                text: sourceBridge.busy ? "Searching…" : "+   Federated Search"
                primary: true
                enabled: !sourceBridge.busy && (center.capabilityCodes || []).length > 0
                onClicked: {
                    selectedIndex = -1
                    searchDialog.sourceCode = ""
                    searchDialog.sourceTitle = "All safe compatible sources"
                    searchDialog.sourceCapabilities = center.capabilityCodes || []
                    searchDialog.requiresVerifiedScope = false
                    searchDialog.open()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 112
            spacing: Spacing.panelGap

            StatCard {
                Layout.fillWidth: true
                title: "Known Sources"
                value: String(counts.total || 0)
                delta: ""
                subtext: "Runtime executors + catalog-only entries"
                iconSource: "../../assets/icons/database.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Ready"
                value: String(counts.ready || 0)
                delta: ""
                subtext: "Configured or locally available"
                iconSource: "../../assets/icons/globe_green.svg"
                accentColor: Theme.success
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Federation"
                value: String(counts.remoteAdapters || 0)
                delta: ""
                subtext: String(counts.capabilities || 0) + " searchable capabilities"
                iconSource: "../../assets/icons/globe_blue.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Other Runtime"
                value: String(Number(counts.classicConnectors || 0) + Number(counts.registryProviders || 0) + Number(counts.openWebProviders || 0))
                delta: ""
                subtext: "OSINT + Registry + Open-Web"
                iconSource: "../../assets/icons/graph_blue.svg"
                accentColor: Theme.warning
                chartType: "none"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.panelGap

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 630
                Layout.minimumWidth: 520
                title: "Source Center"
                subtitle: String(root.filteredSources().length) + " visible source(s)"
                iconSource: "../../assets/icons/database.svg"

                Item {
                    anchors.fill: parent

                    RowLayout {
                        id: filters
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 12
                        height: 42
                        spacing: 8

                        AppTextField {
                            Layout.fillWidth: true
                            placeholderText: "Filter sources, capabilities, countries…"
                            onTextChanged: { root.filterText = text; root.selectedIndex = -1 }
                        }
                        AppComboBox {
                            Layout.preferredWidth: 155
                            model: ["All", "Federation", "Classic OSINT", "Open Web", "Registry", "Catalog"]
                            onCurrentTextChanged: { root.subsystemFilter = currentText; root.selectedIndex = -1 }
                        }
                    }

                    ListView {
                        id: sourceList
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: filters.bottom
                        anchors.bottom: parent.bottom
                        anchors.topMargin: 8
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.filteredSources()
                        currentIndex: root.selectedIndex

                        delegate: Rectangle {
                            id: sourceRow
                            required property var modelData
                            required property int index
                            width: sourceList.width
                            height: 86
                            color: ListView.isCurrentItem ? Theme.accentSoft : (rowMouse.containsMouse ? Theme.surfaceHover : "transparent")

                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                            Rectangle { x: 16; y: 18; width: 4; height: 50; radius: 2; color: root.statusColor(sourceRow.modelData) }

                            Text {
                                x: 32; y: 12; width: parent.width - 220
                                text: String(sourceRow.modelData.title || sourceRow.modelData.code || "Source")
                                color: Theme.textPrimary; font.pixelSize: 13; font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 32; y: 35; width: parent.width - 220
                                text: String(sourceRow.modelData.subsystem || "") + " · " + String(sourceRow.modelData.capabilitiesText || "No runtime capability")
                                color: Theme.textSecondary; font.pixelSize: 10; elide: Text.ElideRight
                            }
                            Text {
                                x: 32; y: 58; width: parent.width - 220
                                text: String(sourceRow.modelData.countriesText || "GLOBAL") + " · " + root.pretty(sourceRow.modelData.accessMode || "") + " · " + root.pretty(sourceRow.modelData.implementationStatus || "")
                                color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight
                            }

                            Rectangle {
                                anchors.right: parent.right; anchors.rightMargin: 16; anchors.top: parent.top; anchors.topMargin: 14
                                width: Math.max(78, runtimeLabel.implicitWidth + 20); height: 24; radius: 6
                                color: "transparent"; border.width: 1; border.color: root.statusColor(sourceRow.modelData)
                                Text { id: runtimeLabel; anchors.centerIn: parent; text: String(sourceRow.modelData.runtimeStatus || "Unknown"); color: root.statusColor(sourceRow.modelData); font.pixelSize: 9 }
                            }
                            Text {
                                anchors.right: parent.right; anchors.rightMargin: 16; anchors.bottom: parent.bottom; anchors.bottomMargin: 14
                                text: root.sourceActionLabel(sourceRow.modelData)
                                color: Boolean(sourceRow.modelData.searchable) ? Theme.accent : Theme.textMuted
                                font.pixelSize: 9
                            }

                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedIndex = sourceRow.index
                                onDoubleClicked: {
                                    root.selectedIndex = sourceRow.index
                                    const row = sourceRow.modelData
                                    if (Boolean(row.searchable)) {
                                        searchDialog.sourceCode = String(row.code || "")
                                        searchDialog.sourceTitle = String(row.title || row.code || "Selected source")
                                        searchDialog.sourceCapabilities = row.capabilities || []
                                        searchDialog.requiresVerifiedScope = Boolean(row.requiresVerifiedScope)
                                        searchDialog.open()
                                    } else if (String(row.routePage || "") === "registry") {
                                        desktopBridge.navigateTo("registry")
                                    } else if (String(row.routePage || "") === "osint") {
                                        desktopBridge.navigateTo("osint")
                                    }
                                }
                            }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Federated Results"
                subtitle: Boolean(runData.hasRun)
                    ? (root.pretty(runData.capability || "") + " · " + String(runData.value || ""))
                    : "Run a safe automatic or explicit Federation query"
                iconSource: "../../assets/icons/globe_blue.svg"

                Item {
                    anchors.fill: parent

                    Row {
                        id: resultTabs
                        anchors.left: parent.left; anchors.top: parent.top; anchors.leftMargin: 14; anchors.topMargin: 10
                        spacing: 6
                        Repeater {
                            model: [
                                { key: "records", label: "Records", count: Number(runSummary.records || 0) },
                                { key: "providers", label: "Providers", count: Number(runSummary.providers || 0) }
                            ]
                            delegate: Rectangle {
                                id: resultTabButton
                                required property var modelData
                                property bool selected: root.resultTab === String(modelData.key)
                                width: tabText.implicitWidth + 24; height: 28; radius: 6
                                color: selected ? Theme.accentSoft : "transparent"
                                border.color: selected ? Theme.accent : "transparent"
                                Text { id: tabText; anchors.centerIn: parent; text: String(resultTabButton.modelData.label) + "  " + String(resultTabButton.modelData.count); color: resultTabButton.selected ? Theme.textPrimary : Theme.textSecondary; font.pixelSize: 10 }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.resultTab = String(resultTabButton.modelData.key) }
                            }
                        }
                    }

                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 14; anchors.top: parent.top; anchors.topMargin: 10
                        width: Math.max(86, runState.implicitWidth + 22); height: 28; radius: 6
                        visible: Boolean(runData.hasRun)
                        color: "transparent"; border.width: 1; border.color: root.runStatusColor()
                        Text { id: runState; anchors.centerIn: parent; text: root.pretty(runData.status || "No run"); color: root.runStatusColor(); font.pixelSize: 9 }
                    }

                    ListView {
                        id: resultList
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: resultTabs.bottom; anchors.bottom: statusStrip.top
                        anchors.topMargin: 10
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.resultTab === "providers" ? (runData.providers || []) : (runData.records || [])
                        visible: Boolean(runData.hasRun) && !sourceBridge.busy

                        delegate: Rectangle {
                            id: resultRow
                            required property var modelData
                            width: resultList.width; height: 82; color: rowMouse2.containsMouse ? Theme.surfaceHover : "transparent"
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                            Text {
                                x: 18; y: 13; width: parent.width - 185
                                text: root.resultTab === "providers" ? String(resultRow.modelData.source || "Provider") : String(resultRow.modelData.title || "Remote record")
                                color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.Medium; elide: Text.ElideRight
                            }
                            Text {
                                x: 18; y: 36; width: parent.width - 185
                                text: root.resultTab === "providers"
                                    ? (String(resultRow.modelData.error || "") || (String(resultRow.modelData.records || 0) + " record(s)"))
                                    : (String(resultRow.modelData.detail || "") || String(resultRow.modelData.identifiersText || ""))
                                color: Theme.textSecondary; font.pixelSize: 10; elide: Text.ElideRight
                            }
                            Text {
                                x: 18; y: 58; width: parent.width - 185
                                text: root.resultTab === "providers"
                                    ? "raw secrets stored: NO"
                                    : (String(resultRow.modelData.source || "") + " · " + root.pretty(resultRow.modelData.type || "record"))
                                color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight
                            }
                            Rectangle {
                                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(80, badgeText.implicitWidth + 20); height: 24; radius: 6
                                color: "transparent"; border.width: 1; border.color: Theme.accent
                                Text {
                                    id: badgeText; anchors.centerIn: parent
                                    text: root.resultTab === "providers" ? root.pretty(resultRow.modelData.status || "") : String(resultRow.modelData.country || "GLOBAL")
                                    color: Theme.accent; font.pixelSize: 9
                                }
                            }
                            MouseArea {
                                id: rowMouse2; anchors.fill: parent; hoverEnabled: true
                                cursorShape: (root.resultTab === "records" && String(resultRow.modelData.sourceUrl || "").length > 0) ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (root.resultTab === "records" && String(resultRow.modelData.sourceUrl || "").length > 0)
                                        desktopBridge.openExternalUrl(String(resultRow.modelData.sourceUrl))
                                }
                            }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    EmptyState {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: resultTabs.bottom; anchors.bottom: statusStrip.top
                        anchors.margins: 18
                        visible: !Boolean(runData.hasRun)
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "No federated search yet"
                        description: "Select a Federation source or use Search all safe compatible sources. Contract and verified-scope sources are never executed accidentally."
                    }
                    EmptyState {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: resultTabs.bottom; anchors.bottom: statusStrip.top
                        anchors.margins: 18
                        visible: sourceBridge.busy
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "Federated search in progress"
                        description: "The query is running in a background worker. One provider failure will not stop the others."
                    }
                    EmptyState {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: resultTabs.bottom; anchors.bottom: statusStrip.top
                        anchors.margins: 18
                        visible: Boolean(runData.hasRun) && !sourceBridge.busy && resultList.count === 0
                        iconSource: "../../assets/icons/document_blue.svg"
                        title: root.resultTab === "providers" ? "No provider executions" : "No records returned"
                        description: String(runData.error || "No compatible configured source returned a result for this query.")
                    }

                    Rectangle {
                        id: statusStrip
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        height: 52; color: Theme.surfaceHover
                        border.width: 1; border.color: Theme.divider; radius: 8
                        Text {
                            anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 28
                            text: Boolean(runData.hasRun)
                                ? ("Success " + String(runSummary.successful || 0)
                                   + " · Partial " + String(runSummary.partial || 0)
                                   + " · Not configured " + String(runSummary.notConfigured || 0)
                                   + " · Failed " + String(runSummary.failed || 0)
                                   + " · Raw secrets stored: NO")
                                : sourceBridge.message
                            color: Theme.textSecondary; font.pixelSize: 9; elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }

    AppDialog {
        id: searchDialog
        width: 520
        title: "Federated source search"
        description: sourceCode.length > 0
            ? ("Search only “" + sourceTitle + "”.")
            : "Search every safe automatic Federation adapter compatible with the selected capability."
        primaryText: "Run Search"
        bodyHeight: 392

        property string sourceCode: ""
        property string sourceTitle: "All safe compatible sources"
        property var sourceCapabilities: []
        property bool requiresVerifiedScope: false

        onOpened: {
            targetInput.forceActiveFocus()
            capabilityBox.currentIndex = 0
            verifiedBox.checked = false
        }

        onAccepted: {
            if (sourceBridge.busy) return
            const target = targetInput.text.trim()
            if (target.length === 0 || capabilityBox.currentIndex < 0) {
                open(); targetInput.forceActiveFocus(); return
            }
            const capability = String(searchDialog.sourceCapabilities[capabilityBox.currentIndex] || "")
            const ok = sourceBridge.search(
                capability,
                target,
                countryInput.text.trim(),
                searchDialog.sourceCode,
                verifiedBox.checked
            )
            if (ok) {
                targetInput.clear()
                countryInput.clear()
                root.resultTab = "records"
            } else {
                open()
            }
        }

        Column {
            anchors.fill: parent
            anchors.leftMargin: 22; anchors.rightMargin: 22; anchors.topMargin: 16; anchors.bottomMargin: 14
            spacing: 7

            Text { text: "SOURCE"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.2 }
            Text { width: parent.width; text: searchDialog.sourceTitle; color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.Medium; elide: Text.ElideRight }
            Item { width: 1; height: 3 }

            Text { text: "CAPABILITY"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.2 }
            AppComboBox {
                id: capabilityBox
                width: parent.width
                model: searchDialog.sourceCapabilities
            }

            Text { text: "TARGET VALUE"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.2 }
            AppTextField { id: targetInput; width: parent.width; placeholderText: "Email, username, domain, IP, CVE, DOI, name, identifier…"; Keys.onReturnPressed: searchDialog.accept() }

            Text { text: "COUNTRY (OPTIONAL)"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.2 }
            AppTextField { id: countryInput; width: parent.width; placeholderText: "ISO-2, e.g. US / GB / FR"; maximumLength: 2 }

            CheckBox {
                id: verifiedBox
                visible: searchDialog.requiresVerifiedScope
                text: "I confirm this query is within an authorized / verified scope"
                checked: false
                contentItem: Text { text: verifiedBox.text; color: Theme.warning; font.pixelSize: 10; leftPadding: verifiedBox.indicator.width + verifiedBox.spacing }
            }

            Text {
                width: parent.width
                wrapMode: Text.Wrap
                color: searchDialog.requiresVerifiedScope ? Theme.warning : Theme.textMuted
                font.pixelSize: 9
                text: searchDialog.requiresVerifiedScope
                    ? "This provider is blocked until verified scope is explicitly confirmed."
                    : (searchDialog.sourceCode.length > 0
                        ? "Explicit source selection may use configured contract/free-key sources, but secrets remain sanitized and are not persisted by this UI search."
                        : "Safe automatic mode excludes sources that opt out of automatic execution, including verified-scope/contract-sensitive operations.")
            }
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.textSecondary; font.pixelSize: 9; text: sourceBridge.message; maximumLineCount: 2; elide: Text.ElideRight }
        }
    }
}
