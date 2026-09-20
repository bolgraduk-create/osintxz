pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var center: registryBridge.registryCenter || ({})
    property var runData: registryBridge.runData || ({})
    property var summary: runData.summary || ({})
    property var persistence: runData.persistence || ({})
    property var records: runData.records || []
    property var providers: center.providers || []
    property int selectedIndex: root.activeTab === "results" && records.length > 0 ? Math.min(resultView.currentIndex < 0 ? 0 : resultView.currentIndex, records.length - 1) : -1
    property var selectedRecord: selectedIndex >= 0 ? records[selectedIndex] : ({})
    property string activeTab: "results"

    function codeAt(codes, index) {
        return index >= 0 && codes && index < codes.length ? String(codes[index] || "") : ""
    }

    function selectedDomainCode() {
        return codeAt(center.domainCodes || [], domainBox.currentIndex)
    }

    function selectedKindCode() {
        return codeAt(center.queryKindCodes || [], kindBox.currentIndex)
    }

    function selectedSourceCode() {
        if (sourceBox.currentIndex <= 0) return ""
        return codeAt(center.providerCodes || [], sourceBox.currentIndex - 1)
    }

    function sourceModel() {
        const labels = ["AUTO · all safe compatible"]
        const incoming = center.providerLabels || []
        for (let i = 0; i < incoming.length; ++i)
            labels.push(String(incoming[i]))
        return labels
    }

    function sourceLabel(code) {
        const codes = center.providerCodes || []
        const labels = center.providerLabels || []
        const normalized = String(code || "")
        for (let i = 0; i < codes.length; ++i) {
            if (String(codes[i]) === normalized)
                return String(labels[i] || normalized)
        }
        return normalized.length > 0 ? normalized.replace(/_/g, " ") : "Unknown provider"
    }

    function statusLabel() {
        const status = String(runData.status || "")
        if (status === "running") return "Running"
        if (status === "saving") return "Saving"
        if (status === "completed") return "Completed"
        if (status === "completed_with_errors") return "Completed with warnings"
        if (status === "failed") return "Failed"
        return "No run"
    }

    function statusColor() {
        const status = String(runData.status || "")
        if (status === "running" || status === "saving") return Theme.accent
        if (status === "completed") return Theme.success
        if (status === "completed_with_errors") return Theme.warning
        if (status === "failed") return Theme.danger
        return Theme.textMuted
    }

    function confidenceText(value) {
        const number = Number(value || 0)
        if (!isFinite(number)) return "—"
        return Math.round(number * 100) + "%"
    }

    function recordBadge(record) {
        if (Boolean(record.sensitiveLegalData)) return "LEGAL · REVIEW"
        if (Boolean(record.candidateOnly)) return "CANDIDATE"
        return "RECORD"
    }

    function recordColor(record) {
        if (Boolean(record.sensitiveLegalData)) return Theme.warning
        if (Boolean(record.candidateOnly)) return Theme.warning
        return Theme.success
    }

    function providerStatusColor(status) {
        const value = String(status || "")
        if (value === "success") return Theme.success
        if (value === "partial") return Theme.warning
        if (value === "failed" || value === "not_supported") return Theme.danger
        return Theme.textMuted
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
                text: "OFFICIAL & PUBLIC RECORDS"
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 1
                y: 20
                text: "Registry Intelligence"
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Text {
                x: 2
                y: 57
                text: "Search every compatible Registry provider through one policy-aware router."
                color: Theme.textSecondary
                font.pixelSize: 13
            }

            AppButton {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 126
                height: 38
                text: "Refresh Sources"
                enabled: !registryBridge.busy
                onClicked: registryBridge.refresh()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 108
            spacing: Spacing.panelGap

            StatCard {
                Layout.fillWidth: true
                title: "Providers"
                value: String((center.counts || {}).providers || 0)
                delta: ""
                subtext: String((center.counts || {}).ready || 0) + " ready in current runtime"
                iconSource: "../../assets/icons/database.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Automatic"
                value: String((center.counts || {}).automatic || 0)
                delta: ""
                subtext: "Safe providers eligible for AUTO routing"
                iconSource: "../../assets/icons/globe_blue.svg"
                accentColor: Theme.success
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Countries"
                value: String((center.counts || {}).countries || 0)
                delta: ""
                subtext: "Plus global-scope sources"
                iconSource: "../../assets/icons/pin_purple.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Last Run"
                value: Boolean(runData.hasRun) ? root.statusLabel() : "—"
                delta: ""
                subtext: Boolean(runData.hasRun)
                    ? String(runData.value || "")
                    : "No Registry query in this session"
                iconSource: "../../assets/icons/chart.svg"
                accentColor: root.statusColor()
                chartType: "none"
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            title: "Search Registries"
            subtitle: "AUTO searches every safe compatible provider; choose a provider to run it explicitly."
            iconSource: "../../assets/icons/search.svg"

            GridLayout {
                anchors.fill: parent
                anchors.margins: 16
                columns: 5
                columnSpacing: 10
                rowSpacing: 8

                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "DOMAIN"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                    AppComboBox {
                        id: domainBox
                        Layout.fillWidth: true
                        model: center.domainLabels || []
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "QUERY KIND"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                    AppComboBox {
                        id: kindBox
                        Layout.fillWidth: true
                        model: center.queryKindLabels || []
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "COUNTRY (OPTIONAL)"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                    AppTextField {
                        id: countryInput
                        Layout.fillWidth: true
                        placeholderText: "UA / US / GB / PL / blank"
                        maximumLength: 2
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 280
                    Text { text: "SOURCE"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                    AppComboBox {
                        id: sourceBox
                        Layout.fillWidth: true
                        model: root.sourceModel()
                    }
                }
                Item {
                    Layout.preferredWidth: 150
                    Layout.fillHeight: true
                    AppButton {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 42
                        text: registryBridge.busy ? "Running…" : "Run Search"
                        primary: true
                        enabled: !registryBridge.busy
                            && queryInput.text.trim().length > 0
                            && domainBox.currentIndex >= 0
                            && kindBox.currentIndex >= 0
                        onClicked: {
                            root.activeTab = "results"
                            resultView.currentIndex = -1
                            registryBridge.search(
                                root.selectedDomainCode(),
                                root.selectedKindCode(),
                                queryInput.text.trim(),
                                countryInput.text.trim(),
                                root.selectedSourceCode()
                            )
                        }
                    }
                }

                ColumnLayout {
                    Layout.columnSpan: 5
                    Layout.fillWidth: true
                    Text { text: "VALUE"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                    AppTextField {
                        id: queryInput
                        Layout.fillWidth: true
                        placeholderText: "Company name, LEI, VAT, registration ID, case number…"
                        Keys.onReturnPressed: {
                            if (!registryBridge.busy && text.trim().length > 0)
                                registryBridge.search(root.selectedDomainCode(), root.selectedKindCode(), text.trim(), countryInput.text.trim(), root.selectedSourceCode())
                        }
                    }
                }
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
                title: root.activeTab === "providers" ? "Registry Providers" : "Registry Results"
                subtitle: root.activeTab === "providers"
                    ? "Live capabilities from RegistryProviderRegistry"
                    : (Boolean(runData.hasRun)
                        ? String(summary.records || 0) + " record(s) · " + String(runData.durationText || "")
                        : "Run a provider-aware registry query")
                iconSource: "../../assets/icons/document_blue.svg"

                Item {
                    anchors.fill: parent

                    Row {
                        id: tabs
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.leftMargin: 14
                        anchors.topMargin: 8
                        spacing: 6

                        Repeater {
                            model: [
                                { key: "results", label: "Results" },
                                { key: "providers", label: "Providers" }
                            ]
                            delegate: Rectangle {
                                id: tab
                                required property var modelData
                                property bool selected: root.activeTab === String(modelData.key)
                                width: tabText.implicitWidth + 24
                                height: 28
                                radius: 6
                                color: selected ? Theme.accentSoft : (tabMouse.containsMouse ? Theme.surfaceHover : "transparent")
                                border.color: selected ? Theme.accent : "transparent"
                                Text {
                                    id: tabText
                                    anchors.centerIn: parent
                                    text: String(tab.modelData.label)
                                    color: tab.selected ? Theme.textPrimary : Theme.textSecondary
                                    font.pixelSize: 10
                                    font.weight: tab.selected ? Font.Medium : Font.Normal
                                }
                                MouseArea {
                                    id: tabMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.activeTab = String(tab.modelData.key)
                                }
                            }
                        }
                    }

                    ListView {
                        id: resultView
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: tabs.bottom
                        anchors.bottom: parent.bottom
                        anchors.topMargin: 8
                        clip: true
                        spacing: 0
                        model: root.activeTab === "providers" ? root.providers : root.records
                        currentIndex: -1
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            id: row
                            required property var modelData
                            required property int index
                            width: resultView.width
                            height: root.activeTab === "providers" ? 84 : 92
                            color: resultView.currentIndex === row.index && root.activeTab === "results"
                                ? Theme.accentSoft : "transparent"

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }

                            Rectangle {
                                x: 16
                                y: 18
                                width: 4
                                height: parent.height - 36
                                radius: 2
                                color: root.activeTab === "providers"
                                    ? (Boolean(row.modelData.configured) ? Theme.success : Theme.warning)
                                    : root.recordColor(row.modelData)
                            }

                            Text {
                                x: 32
                                y: 14
                                width: parent.width - 230
                                text: root.activeTab === "providers"
                                    ? String(row.modelData.title || row.modelData.code || "Registry provider")
                                    : String(row.modelData.title || "Registry record")
                                color: Theme.textPrimary
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 32
                                y: 38
                                width: parent.width - 230
                                text: root.activeTab === "providers"
                                    ? (String(row.modelData.domainsText || "") + " · " + String(row.modelData.queryKindsText || ""))
                                    : String(row.modelData.detail || "Official/public registry record")
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 32
                                y: 61
                                width: parent.width - 230
                                text: root.activeTab === "providers"
                                    ? (String(row.modelData.countriesText || "GLOBAL") + " · " + String(row.modelData.accessMode || ""))
                                    : (root.sourceLabel(String(row.modelData.provider || ""))
                                        + (String(row.modelData.identifiersText || "").length > 0 ? " · " + String(row.modelData.identifiersText) : ""))
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }

                            Rectangle {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.top: parent.top
                                anchors.topMargin: 17
                                width: Math.max(86, badge.implicitWidth + 20)
                                height: 24
                                radius: 12
                                color: "transparent"
                                border.width: 1
                                border.color: root.activeTab === "providers"
                                    ? (Boolean(row.modelData.configured) ? Theme.success : Theme.warning)
                                    : root.recordColor(row.modelData)
                                Text {
                                    id: badge
                                    anchors.centerIn: parent
                                    text: root.activeTab === "providers"
                                        ? String(row.modelData.runtimeStatus || "Provider")
                                        : root.recordBadge(row.modelData)
                                    color: root.activeTab === "providers"
                                        ? (Boolean(row.modelData.configured) ? Theme.success : Theme.warning)
                                        : root.recordColor(row.modelData)
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 15
                                text: root.activeTab === "providers"
                                    ? ("Trust " + root.confidenceText(row.modelData.trustScore))
                                    : ("Trust " + root.confidenceText(row.modelData.trustScore))
                                color: Theme.textMuted
                                font.pixelSize: 9
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: root.activeTab === "results" ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (root.activeTab === "results")
                                        resultView.currentIndex = row.index
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    EmptyState {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: tabs.bottom
                        anchors.bottom: parent.bottom
                        anchors.margins: 18
                        visible: resultView.count === 0 && !registryBridge.busy
                        iconSource: "../../assets/icons/document_blue.svg"
                        title: root.activeTab === "providers"
                            ? "No Registry providers registered"
                            : (Boolean(runData.hasRun) ? "No registry matches" : "Search official/public registries")
                        description: root.activeTab === "providers"
                            ? "The ServiceContainer did not expose any Registry providers."
                            : "AUTO mode routes the query only to compatible providers allowed by access policy."
                    }

                    EmptyState {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: tabs.bottom
                        anchors.bottom: parent.bottom
                        anchors.margins: 18
                        visible: registryBridge.busy && String(runData.status || "") === "running"
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "Registry search in progress"
                        description: "Each provider is isolated; one upstream failure does not stop the remaining registry search."
                    }
                }
            }

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 410
                Layout.maximumWidth: 450
                title: "Result / Route Details"
                subtitle: root.selectedIndex >= 0
                    ? root.sourceLabel(String(root.selectedRecord.provider || ""))
                    : "Provider execution and safety context"
                iconSource: "../../assets/icons/chart.svg"

                Item {
                    anchors.fill: parent

                    Flickable {
                        anchors.fill: parent
                        clip: true
                        contentWidth: width
                        contentHeight: details.height
                        boundsBehavior: Flickable.StopAtBounds

                        Column {
                            id: details
                            width: parent.width
                            spacing: 0

                            Rectangle {
                                width: parent.width
                                height: root.selectedIndex >= 0 && (Boolean(root.selectedRecord.sensitiveLegalData) || Boolean(root.selectedRecord.candidateOnly)) ? 96 : 0
                                visible: height > 0
                                color: "transparent"
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    radius: 8
                                    color: "#3b3015"
                                    border.width: 1
                                    border.color: Theme.warning
                                }
                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    wrapMode: Text.Wrap
                                    color: Theme.warning
                                    font.pixelSize: 10
                                    text: Boolean(root.selectedRecord.sensitiveLegalData)
                                        ? "Sensitive legal record. A case/decision match does not establish identity, guilt, liability or conviction. Review provenance independently."
                                        : "Candidate match. Name-only or otherwise weak identity signals are not treated as confirmed identity."
                                }
                            }

                            Repeater {
                                model: root.selectedIndex >= 0 ? [
                                    { label: "TITLE", value: root.selectedRecord.title || "—" },
                                    { label: "PROVIDER", value: root.sourceLabel(root.selectedRecord.provider || "") },
                                    { label: "TYPE", value: String(root.selectedRecord.entityKind || "—").replace(/_/g, " ").toUpperCase() },
                                    { label: "STATUS", value: root.selectedRecord.status || "—" },
                                    { label: "IDENTIFIERS", value: root.selectedRecord.identifiersText || "—" },
                                    { label: "COUNTRY / JURISDICTION", value: (root.selectedRecord.country || "—") + " / " + (root.selectedRecord.jurisdiction || "—") },
                                    { label: "TRUST / CONFIDENCE", value: root.confidenceText(root.selectedRecord.trustScore) + " / " + root.confidenceText(root.selectedRecord.confidence) },
                                    { label: "RAW REFERENCE", value: root.selectedRecord.rawReference || "—" },
                                    { label: "RETRIEVED", value: root.selectedRecord.retrievedAt || "—" },
                                    { label: "SOURCE URL", value: root.selectedRecord.sourceUrl || "—", isUrl: Boolean(root.selectedRecord.sourceUrl) }
                                ] : [
                                    { label: "STATUS", value: root.statusLabel() },
                                    { label: "PROVIDER EXECUTIONS", value: String(root.summary.providerExecutions || 0) },
                                    { label: "BLOCKED BY POLICY / CONFIG", value: String(root.summary.blocked || 0) },
                                    { label: "PROVIDER ERRORS", value: String(root.summary.providerErrors || 0) },
                                    { label: "CANDIDATES", value: String(root.summary.candidates || 0) },
                                    { label: "SENSITIVE LEGAL", value: String(root.summary.sensitiveLegal || 0) },
                                    { label: "PERSISTABLE", value: String(root.summary.persistable || 0) },
                                    { label: "MESSAGE", value: registryBridge.message || "—" }
                                ]

                                delegate: Rectangle {
                                    id: detailRow
                                    required property var modelData
                                    width: details.width
                                    height: 58
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
                                        font.letterSpacing: 1.0
                                    }
                                    Text {
                                        x: 18
                                        y: 29
                                        width: parent.width - 36
                                        text: String(detailRow.modelData.value)
                                        color: Boolean(detailRow.modelData.isUrl) ? Theme.accent : Theme.textPrimary
                                        font.pixelSize: 10
                                        font.underline: Boolean(detailRow.modelData.isUrl)
                                        elide: Text.ElideRight
                                        maximumLineCount: 1
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: Boolean(detailRow.modelData.isUrl)
                                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: desktopBridge.openExternalUrl(String(detailRow.modelData.value || ""))
                                    }
                                }
                            }

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: Theme.divider
                                visible: Boolean(runData.hasRun)
                            }

                            Text {
                                visible: Boolean(runData.hasRun)
                                width: parent.width - 36
                                x: 18
                                wrapMode: Text.Wrap
                                text: "Route: " + JSON.stringify(runData.route || {})
                                color: Theme.textMuted
                                font.pixelSize: 9
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            radius: 10
            color: Theme.surfaceHover
            border.width: 1
            border.color: Theme.divider

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - saveButton.width - 220
                text: desktopBridge.hasCurrentCase
                    ? (Boolean(persistence.attempted)
                        ? ("Last save → evidence " + Number(persistence.evidencesCreated || 0)
                            + ", entities " + Number(persistence.entitiesCreated || 0)
                            + ", links " + Number(persistence.linksCreated || 0)
                            + ", skipped " + Number(persistence.skippedRecords || 0))
                        : ("Selected investigation: " + desktopBridge.currentCaseTitle))
                    : "Search works without a selected case. Select an investigation only when you want to persist reviewed records."
                color: Theme.textSecondary
                font.pixelSize: 10
                elide: Text.ElideRight
            }

            AppButton {
                id: saveButton
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 188
                height: 36
                text: registryBridge.busy && String(runData.status || "") === "saving"
                    ? "Saving…" : "Save to Investigation"
                primary: true
                enabled: !registryBridge.busy
                    && desktopBridge.hasCurrentCase
                    && Boolean(runData.hasRun)
                    && (String(runData.status || "") === "completed" || String(runData.status || "") === "completed_with_errors")
                    && Number(summary.persistable || 0) > 0
                ToolTip.visible: hovered && !enabled
                ToolTip.delay: 450
                ToolTip.text: !desktopBridge.hasCurrentCase
                    ? "Select an investigation first."
                    : Number(summary.persistable || 0) < 1
                        ? "No verified/persistable records in the current result."
                        : "Wait for the current Registry operation to finish."
                onClicked: registryBridge.persistLast(desktopBridge.currentCaseId)
            }
        }
    }
}
