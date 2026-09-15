pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var runData: desktopBridge.registryRun || ({})
    property var records: runData.records || []
    property var summary: runData.summary || ({})
    property var persistence: runData.persistence || ({})
    property bool busy: desktopBridge.registryBusy
    property bool hasRun: Boolean(runData.hasRun)
    property int selectedIndex: -1
    property var selectedRecord: selectedIndex >= 0 && selectedIndex < records.length ? records[selectedIndex] : ({})

    onRecordsChanged: {
        if (root.records.length === 0)
            root.selectedIndex = -1
        else if (root.selectedIndex < 0 || root.selectedIndex >= root.records.length)
            root.selectedIndex = 0
    }

    function placeholderForMode() {
        const mode = String(modeBox.currentText || "")
        if (mode === "EDRPOU") return "14359609"
        if (mode === "Company name") return "Company name"
        if (mode === "FOP name") return "Surname Name Patronymic"
        if (mode === "Court case number") return "260/7098/24"
        return "Registry query"
    }

    function statusLabel() {
        const status = String(runData.status || "")
        if (status === "running") return "Searching"
        if (status === "saving") return "Saving"
        if (status === "completed") return "Completed"
        if (status === "completed_with_errors") return "Completed with warnings"
        if (status === "failed") return "Failed"
        return "Ready"
    }

    function statusColor() {
        const status = String(runData.status || "")
        if (status === "running" || status === "saving") return Theme.accent
        if (status === "completed") return Theme.success
        if (status === "completed_with_errors") return Theme.warning
        if (status === "failed") return Theme.danger
        return Theme.textMuted
    }

    function recordBadge(record) {
        if (Boolean(record.sensitiveLegalData)) return "LEGAL · REVIEW"
        if (Boolean(record.candidateOnly)) return "CANDIDATE"
        if (String(record.entityKind || "") === "company") return "COMPANY"
        if (String(record.entityKind || "") === "sole_trader") return "FOP"
        return String(record.entityKind || "RECORD").replace(/_/g, " ").toUpperCase()
    }

    function recordBadgeColor(record) {
        if (Boolean(record.sensitiveLegalData)) return Theme.warning
        if (Boolean(record.candidateOnly)) return Theme.warning
        return Theme.success
    }

    function confidenceText(value) {
        const number = Number(value || 0)
        return Math.round(number * 100) + "%"
    }

    function sourceLabel(provider) {
        if (provider === "ua_edr_business") return "Ukraine EDR"
        if (provider === "ua_edrsr") return "Ukraine EDRSR"
        return String(provider || "Registry")
    }

    function searchCurrent() {
        const value = queryInput.text.trim()
        if (value.length === 0) {
            queryInput.forceActiveFocus()
            return
        }
        root.selectedIndex = -1
        desktopBridge.registrySearch(modeBox.currentText, value)
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
            Layout.minimumHeight: 75
            Layout.maximumHeight: 75

            Text {
                x: 1
                y: 0
                text: "OFFICIAL DATA SOURCES"
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
                text: "Search bounded official registry records through the central Registry Backend."
                color: Theme.textSecondary
                font.pixelSize: 13
            }

            AppButton {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 126
                height: 38
                text: "←   OSINT"
                enabled: !root.busy
                onClicked: desktopBridge.openOsint()
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.preferredHeight: 176
            Layout.minimumHeight: 176
            Layout.maximumHeight: 176
            title: "Registry Query"
            subtitle: "Ukraine EDR and Unified State Register of Court Decisions"
            iconSource: "../../assets/icons/globe_blue.svg"

            Item {
                anchors.fill: parent

                RowLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    anchors.topMargin: 12
                    spacing: 12

                    ColumnLayout {
                        Layout.preferredWidth: 230
                        spacing: 6

                        Text {
                            text: "QUERY TYPE"
                            color: Theme.textMuted
                            font.pixelSize: 9
                            font.weight: Font.Medium
                            font.letterSpacing: 1.1
                        }

                        AppComboBox {
                            id: modeBox
                            objectName: "registryQueryMode"
                            Layout.fillWidth: true
                            model: ["EDRPOU", "Company name", "FOP name", "Court case number"]
                            enabled: !root.busy
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "VALUE"
                            color: Theme.textMuted
                            font.pixelSize: 9
                            font.weight: Font.Medium
                            font.letterSpacing: 1.1
                        }

                        AppTextField {
                            id: queryInput
                            objectName: "registryQueryInput"
                            Layout.fillWidth: true
                            placeholderText: root.placeholderForMode()
                            enabled: !root.busy
                            Keys.onReturnPressed: root.searchCurrent()
                        }
                    }

                    AppButton {
                        id: searchButton
                        objectName: "registrySearchButton"
                        Layout.preferredWidth: 132
                        Layout.preferredHeight: 38
                        Layout.alignment: Qt.AlignBottom
                        text: root.busy && String(root.runData.status || "") === "running" ? "Searching…" : "Search"
                        primary: true
                        enabled: !root.busy && queryInput.text.trim().length > 0
                        onClicked: root.searchCurrent()
                    }
                }

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    anchors.bottomMargin: 10
                    text: modeBox.currentText === "Company name" || modeBox.currentText === "FOP name"
                        ? "Name-only matches are candidates. They are shown for review but are not persisted as verified evidence."
                        : modeBox.currentText === "Court case number"
                            ? "Court records are sensitive legal data. A match never implies identity, guilt or conviction."
                            : "Exact EDRPOU lookup may be persisted into the selected investigation with provenance."
                    color: modeBox.currentText === "Company name" || modeBox.currentText === "FOP name" || modeBox.currentText === "Court case number"
                        ? Theme.warning : Theme.textMuted
                    font.pixelSize: 10
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 78
            Layout.minimumHeight: 78
            Layout.maximumHeight: 78
            spacing: Spacing.panelGap

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Theme.surfaceHover
                border.width: 1
                border.color: Theme.divider
                Column {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 18
                    spacing: 5
                    Text { text: String(root.summary.records || 0); color: Theme.textPrimary; font.pixelSize: 23; font.weight: Font.DemiBold }
                    Text { text: "MATCHED RECORDS"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.0 }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Theme.surfaceHover
                border.width: 1
                border.color: Theme.divider
                Column {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 18
                    spacing: 5
                    Text { text: String(root.summary.persistable || 0); color: Theme.success; font.pixelSize: 23; font.weight: Font.DemiBold }
                    Text { text: "PERSISTABLE"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.0 }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Theme.surfaceHover
                border.width: 1
                border.color: Theme.divider
                Column {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 18
                    spacing: 5
                    Text { text: String(root.summary.candidates || 0); color: Theme.warning; font.pixelSize: 23; font.weight: Font.DemiBold }
                    Text { text: "CANDIDATES"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.0 }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Theme.surfaceHover
                border.width: 1
                border.color: Theme.divider
                Column {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 18
                    spacing: 5
                    Text { text: root.statusLabel(); color: root.statusColor(); font.pixelSize: 16; font.weight: Font.DemiBold }
                    Text { text: "LAST OPERATION"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 1.0 }
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
                title: "Registry Results"
                subtitle: root.hasRun
                    ? (String(root.summary.records || 0) + " record(s) · " + String(root.runData.durationText || ""))
                    : "Run an official registry query"
                iconSource: "../../assets/icons/document_blue.svg"

                Item {
                    anchors.fill: parent

                    ListView {
                        id: resultsView
                        anchors.fill: parent
                        clip: true
                        model: root.records
                        currentIndex: root.selectedIndex
                        boundsBehavior: Flickable.StopAtBounds
                        spacing: 0

                        delegate: Rectangle {
                            id: resultRow
                            required property var modelData
                            required property int index
                            width: resultsView.width
                            height: 92
                            color: ListView.isCurrentItem ? Theme.accentSoft : "transparent"

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
                                height: 54
                                radius: 2
                                color: root.recordBadgeColor(resultRow.modelData)
                            }

                            Text {
                                x: 32
                                y: 15
                                width: parent.width - 230
                                text: String(resultRow.modelData.title || "Registry record")
                                color: Theme.textPrimary
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 32
                                y: 38
                                width: parent.width - 230
                                text: String(resultRow.modelData.detail || "")
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 32
                                y: 61
                                width: parent.width - 230
                                text: root.sourceLabel(String(resultRow.modelData.provider || ""))
                                    + (String(resultRow.modelData.identifiersText || "").length > 0
                                        ? " · " + String(resultRow.modelData.identifiersText) : "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }

                            Rectangle {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.top: parent.top
                                anchors.topMargin: 18
                                width: badgeText.implicitWidth + 18
                                height: 24
                                radius: 12
                                color: "transparent"
                                border.width: 1
                                border.color: root.recordBadgeColor(resultRow.modelData)

                                Text {
                                    id: badgeText
                                    anchors.centerIn: parent
                                    text: root.recordBadge(resultRow.modelData)
                                    color: root.recordBadgeColor(resultRow.modelData)
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.7
                                }
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 17
                                text: "Trust " + root.confidenceText(resultRow.modelData.trustScore)
                                color: Theme.textMuted
                                font.pixelSize: 9
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedIndex = resultRow.index
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: !root.busy && resultsView.count === 0
                        iconSource: "../../assets/icons/document_blue.svg"
                        title: root.hasRun ? "No registry matches" : "Search official registries"
                        description: root.hasRun
                            ? "No records matched the current bounded query."
                            : "Use an exact EDRPOU, company/FOP name, or court case number."
                    }

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: root.busy && String(root.runData.status || "") === "running"
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "Registry search in progress"
                        description: "The desktop is querying the central Registry Backend."
                    }
                }
            }

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 410
                Layout.maximumWidth: 450
                title: "Record Details"
                subtitle: root.selectedIndex >= 0
                    ? root.sourceLabel(String(root.selectedRecord.provider || ""))
                    : "Provenance and safety context"
                iconSource: "../../assets/icons/chart.svg"

                Item {
                    anchors.fill: parent

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: root.selectedIndex < 0
                        iconSource: "../../assets/icons/chart.svg"
                        title: "No record selected"
                        description: "Select a registry result to inspect identifiers, provenance and safety rules."
                    }

                    Flickable {
                        id: detailsFlick
                        anchors.fill: parent
                        visible: root.selectedIndex >= 0
                        clip: true
                        contentWidth: width
                        contentHeight: detailsColumn.height
                        boundsBehavior: Flickable.StopAtBounds

                        Column {
                            id: detailsColumn
                            width: detailsFlick.width
                            spacing: 0

                            Rectangle {
                                width: parent.width
                                height: root.selectedRecord.sensitiveLegalData ? 88 : root.selectedRecord.candidateOnly ? 74 : 0
                                visible: height > 0
                                color: "transparent"

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    radius: 8
                                    color: "#3b3015"
                                    border.width: 1
                                    border.color: Theme.warning
                                    opacity: 0.9
                                }

                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    wrapMode: Text.Wrap
                                    color: Theme.warning
                                    font.pixelSize: 10
                                    text: root.selectedRecord.sensitiveLegalData
                                        ? "Sensitive legal record. Identity resolution was not attempted. Legal outcome remains UNKNOWN; this result does not imply guilt or conviction."
                                        : "Name-only candidate. Review identity independently before treating it as a verified registry fact."
                                }
                            }

                            Repeater {
                                model: root.selectedIndex < 0 ? [] : [
                                    { label: "TITLE", value: root.selectedRecord.title || "—" },
                                    { label: "TYPE", value: String(root.selectedRecord.entityKind || "—").replace(/_/g, " ").toUpperCase() },
                                    { label: "STATUS", value: root.selectedRecord.status || "—" },
                                    { label: "IDENTIFIERS", value: root.selectedRecord.identifiersText || "—" },
                                    { label: "LEGAL FORM", value: root.selectedRecord.legalForm || "—" },
                                    { label: "COURT", value: root.selectedRecord.courtName || "—" },
                                    { label: "JUDGE", value: root.selectedRecord.judge || "—" },
                                    { label: "DECISION DATE", value: root.selectedRecord.adjudicationDate || "—" },
                                    { label: "CATEGORY", value: root.selectedRecord.categoryName || "—" },
                                    { label: "TRUST / CONFIDENCE", value: root.confidenceText(root.selectedRecord.trustScore) + " / " + root.confidenceText(root.selectedRecord.confidence) },
                                    { label: "RAW REFERENCE", value: root.selectedRecord.rawReference || "—" },
                                    { label: "RETRIEVED", value: root.selectedRecord.retrievedAt || "—" },
                                    { label: "SOURCE URL", value: root.selectedRecord.sourceUrl || "—", isUrl: Boolean(root.selectedRecord.sourceUrl) }
                                ]

                                delegate: Rectangle {
                                    id: detailRow
                                    required property var modelData
                                    width: detailsColumn.width
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
                                        id: detailValue
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
                                        hoverEnabled: true
                                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: desktopBridge.openExternalUrl(String(detailRow.modelData.value || ""))
                                    }
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            Layout.minimumHeight: 54
            Layout.maximumHeight: 54
            radius: 10
            color: Theme.surfaceHover
            border.width: 1
            border.color: Theme.divider

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - saveButton.width - 210
                text: desktopBridge.hasCurrentCase
                    ? (root.persistence.attempted
                        ? ("Last save → evidence " + Number(root.persistence.evidencesCreated || 0)
                            + ", entities " + Number(root.persistence.entitiesCreated || 0)
                            + ", links " + Number(root.persistence.linksCreated || 0)
                            + ", skipped " + Number(root.persistence.skippedRecords || 0))
                        : ("Selected investigation: " + desktopBridge.currentCaseTitle))
                    : "Select an investigation to persist verified registry records. Search is still available without a selected case."
                color: Theme.textSecondary
                font.pixelSize: 10
                elide: Text.ElideRight
            }

            AppButton {
                id: saveButton
                objectName: "registrySaveButton"
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 176
                height: 36
                text: root.busy && String(root.runData.status || "") === "saving"
                    ? "Saving…" : "Save to Investigation"
                primary: true
                enabled: !root.busy
                    && desktopBridge.hasCurrentCase
                    && Boolean(root.runData.hasRun)
                    && (String(root.runData.status || "") === "completed" || String(root.runData.status || "") === "completed_with_errors")
                    && Number(root.summary.persistable || 0) > 0
                ToolTip.visible: hovered && !enabled
                ToolTip.delay: 450
                ToolTip.text: !desktopBridge.hasCurrentCase
                    ? "Select an investigation first."
                    : Number(root.summary.persistable || 0) < 1
                        ? "Current results are candidates only or no verified records were returned."
                        : "Wait for the current registry operation to finish."
                onClicked: desktopBridge.registryPersistLast()
            }
        }
    }
}
