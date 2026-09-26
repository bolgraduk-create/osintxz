pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property string workspaceMode: "investigation"
    property string activeTab: "results"
    property string resultViewMode: "clean"
    property bool advancedFieldsOpen: false
    property bool searchPolicyOpen: false
    // R13.24 ADAPTIVE RELEVANCE
    property var runData: investigationSearchBridge.runData || ({})
    property var summary: runData.summary || ({})
    property var storedResults: []
    property bool busy: investigationSearchBridge.busy
    // R13.23.1 ADD MENTION TO PERSON
    property var selectedMention: ({})
    property var mentionPersonOptions: []
    property string mentionLinkError: ""
    // R13.25b ACCOUNT DETAILS
    property var selectedAccount: ({})
    property var targetPersonOptions: []
    property string selectedTargetPersonId: ""
    property string targetPersonCaseId: ""
    property string targetPersonError: ""
    property var accountEnrichment: investigationSearchBridge.accountEnrichment || ({})
    property bool accountEnrichmentBusy: investigationSearchBridge.accountEnrichmentBusy
    property var accountEnrichmentCapability: ({ available: false, reason: "", site: "" })
    property var socialActivity: investigationSearchBridge.socialActivity || ({})
    property bool socialActivityBusy: investigationSearchBridge.socialActivityBusy
    property var socialActivityCapability: ({ available: false, reason: "", platform: "", username: "" })

    function suggestedPersonName() {
        var parts = [
            String(firstName.text || "").trim(),
            String(middleName.text || "").trim(),
            String(lastName.text || "").trim()
        ]
        var clean = []
        for (var i = 0; i < parts.length; ++i) {
            if (parts[i].length > 0)
                clean.push(parts[i])
        }
        return clean.join(" ")
    }

    function reloadTargetPeople(preferredId) {
        var caseId = String(desktopBridge.currentCaseId || "")
        var wanted = String(preferredId || root.selectedTargetPersonId || "")

        if (caseId !== root.targetPersonCaseId) {
            root.targetPersonCaseId = caseId
            wanted = ""
            root.selectedTargetPersonId = ""
        }

        var rows = caseId.length
            ? investigationSearchBridge.personOptions(caseId)
            : []
        var model = [{ id: "", label: "Select person…" }]
        for (var i = 0; i < rows.length; ++i)
            model.push(rows[i])

        root.targetPersonOptions = model

        var selectedIndex = 0
        if (wanted.length > 0) {
            for (var j = 1; j < model.length; ++j) {
                if (String(model[j].id || "") === wanted) {
                    selectedIndex = j
                    break
                }
            }
        }

        targetPersonBox.currentIndex = selectedIndex
        root.selectedTargetPersonId = selectedIndex > 0
            ? String(model[selectedIndex].id || "")
            : ""
    }

    function selectedTargetPersonLabel() {
        for (var i = 0; i < root.targetPersonOptions.length; ++i) {
            var item = root.targetPersonOptions[i]
            if (String(item.id || "") === root.selectedTargetPersonId)
                return String(item.label || "Person")
        }
        return ""
    }

    function retrievalScheduleRows() {
        const lanes = (((runData.retrievalSchedule || {}).lanes) || [])
        const rows = []
        for (let i = 0; i < lanes.length; ++i) {
            const decisions = (lanes[i].decisions || [])
            for (let j = 0; j < decisions.length; ++j) rows.push(decisions[j])
        }
        return rows
    }

    function resultSectionForTab(tab) {
        if (tab === "results" || tab === "accounts" || tab === "mentions" || tab === "social" || tab === "correlation")
            return "results"
        if (tab === "possible" || tab === "identity" || tab === "candidates" || tab === "triage")
            return "review"
        return "activity"
    }

    function sectionDefaultTab(section) {
        if (section === "review") return "possible"
        if (section === "activity") return "providers"
        return "results"
    }

    function sectionTabs(section) {
        if (section === "results") {
            return [
                { key: "results", label: "Results" },
                { key: "accounts", label: "Accounts" },
                { key: "mentions", label: "Mentions" },
                { key: "social", label: "Social" },
                { key: "correlation", label: "Correlation" }
            ]
        }
        if (section === "review") {
            return [
                { key: "possible", label: "Possible" },
                { key: "triage", label: "Triage" },
                { key: "identity", label: "Identity" },
                { key: "candidates", label: "Candidates" }
            ]
        }
        return [
            { key: "providers", label: "Providers" },
            { key: "pivots", label: "Pivots" },
            { key: "quality", label: "Quality" },
            { key: "exploration", label: "Explore" },
            { key: "schedule", label: "Schedule" },
            { key: "errors", label: "Errors" }
        ]
    }

    function sectionCount(section) {
        const tabs = root.sectionTabs(section)
        let total = 0
        for (let i = 0; i < tabs.length; ++i)
            total += root.itemCount(String(tabs[i].key))
        return total
    }

    function itemCount(tab) {
        if (tab === "results") return (resultViewMode === "raw" ? (runData.rawResults || []) : (runData.results || [])).length
        if (tab === "identity") return (runData.identityCandidates || []).length
        if (tab === "candidates") return (runData.candidates || []).length
        if (tab === "possible") return (runData.possibleResults || []).length
        if (tab === "accounts") return (runData.relatedAccounts || []).length
        if (tab === "quality") return (runData.qualityTrace || []).length
        if (tab === "exploration") return (((runData.explorationGraph || {}).nodes) || []).length
        if (tab === "schedule") return retrievalScheduleRows().length
        if (tab === "mentions") return (runData.mentions || []).length
        if (tab === "social") return ((((runData.socialIntelligence || {}).items) || runData.socialContent || [])).length
        if (tab === "triage") return (runData.triageRows || []).length
        if (tab === "correlation") return (runData.identityCorrelations || []).length + (runData.socialCorrelations || []).length
        if (tab === "providers") return (runData.providers || []).length
        if (tab === "pivots") return (runData.pivots || []).length
        if (tab === "errors") return (runData.errors || []).length
        return 0
    }

    function tabItems() {
        if (activeTab === "results") return resultViewMode === "raw" ? (runData.rawResults || []) : (runData.results || [])
        if (activeTab === "identity") return runData.identityCandidates || []
        if (activeTab === "candidates") return runData.candidates || []
        if (activeTab === "possible") return runData.possibleResults || []
        if (activeTab === "accounts") return runData.relatedAccounts || []
        if (activeTab === "quality") return runData.qualityTrace || []
        if (activeTab === "exploration") return ((runData.explorationGraph || {}).nodes) || []
        if (activeTab === "schedule") return retrievalScheduleRows()
        if (activeTab === "mentions") return runData.mentions || []
        if (activeTab === "social") return (((runData.socialIntelligence || {}).items) || runData.socialContent || [])
        if (activeTab === "triage") return runData.triageRows || []
        if (activeTab === "correlation") return (runData.identityCorrelations || []).concat(runData.socialCorrelations || [])
        if (activeTab === "providers") return runData.providers || []
        if (activeTab === "pivots") return runData.pivots || []
        if (activeTab === "errors") return runData.errors || []
        return []
    }

    function statusColor(status) {
        const value = String(status || "").toLowerCase()
        if (value === "success" || value === "completed" || value === "finding" || value === "registry" || value === "remote" || value === "strong" || value === "supported" || value === "verified") return Theme.success
        if (value === "partial" || value === "guarded" || value === "candidate" || value === "possible" || value === "insufficient" || value === "reported" || value === "unreachable" || value === "likely" || value === "uncertain" || value === "blocked") return Theme.warning
        if (value === "failed" || value === "conflicting" || value === "invalid") return Theme.danger
        if (value === "not_configured" || value === "not_supported") return Theme.textMuted
        return Theme.accent
    }

    function rowTitle(row) {
        if (activeTab === "identity") return String(row.title || "Identity candidate")
        if (activeTab === "candidates") return String(row.title || "Review candidate")
        if (activeTab === "possible") return String(row.title || "Possible result")
        if (activeTab === "accounts") return String(row.title || row.value || "Related account")
        if (activeTab === "quality") return String(row.title || "Quality observation")
        if (activeTab === "exploration") return String(row.kind || "pivot").toUpperCase() + ": " + String(row.value || "")
        if (activeTab === "schedule") return String(row.seedKind || "seed").replace(/_/g, " ").toUpperCase() + ": " + String(row.seedValue || "")
        if (activeTab === "mentions") return String(row.title || "Corroborating mention")
        if (activeTab === "social") return String(row.author || "Unknown author") + (row.platform ? " · " + String(row.platform) : "")
        if (activeTab === "triage") return String(row.title || row.value || "Identity candidate")
        if (activeTab === "correlation") return String(row.clusterValue || row.leftAuthor || "Correlation signal")
        if (activeTab === "providers") return String(row.source || "Provider")
        if (activeTab === "pivots") return String(row.value || "Pivot")
        if (activeTab === "errors") return String(row.source || row.lane || "Error")
        return String(row.title || "Result")
    }

    function rowDetail(row) {
        if (activeTab === "identity") return String(row.identitySummary || row.detail || "No independent identity signals available")
        if (activeTab === "candidates") return String(row.detail || "Candidate result kept for analyst review")
        if (activeTab === "possible") return String(row.accountVerificationReason || row.visibilityReason || row.detail || "Potentially useful result; analyst review required")
        if (activeTab === "accounts") return String(row.accountVerificationReason || row.detail || "Online account linked by an exact username/account signal")
        if (activeTab === "quality") return String(row.qualitySummary || row.detail || "Shadow quality assessment")
        if (activeTab === "exploration") return String(row.reason || "Quality-approved ephemeral pivot")
        if (activeTab === "schedule") return String(row.reason || "Retrieval scheduling decision")
        if (activeTab === "mentions") return String(row.mentionSummary || row.detail || "Multiple known-person signals occur in this source")
        if (activeTab === "social") return String(row.text || "Public social content")
        if (activeTab === "triage") return String(row.triageSummary || row.detail || "Identity candidate awaiting analyst review")
        if (activeTab === "correlation") return String(row.correlationSummary || "Cross-source context overlap; supporting evidence only")
        if (activeTab === "providers") return String(row.lane || "") + " · " + String(row.detail || "") + (row.healthAction ? " · " + String(row.healthAction) : "")
        if (activeTab === "pivots") return String(row.kind || "pivot").replace(/_/g, " ").toUpperCase() + " · " + String(row.origin || "discovered")
        if (activeTab === "errors") return String(row.error || "Unknown error")
        return String(row.detail || "")
    }

    function rowBadge(row) {
        if (activeTab === "identity") return String(row.identityLabel || row.identityStatus || "IDENTITY").replace(/_/g, " ").toUpperCase()
        if (activeTab === "candidates") return "REVIEW"
        if (activeTab === "possible") return "POSSIBLE"
        if (activeTab === "accounts") return String(row.accountVerificationStatus || "reported").replace(/_/g, " ").toUpperCase()
        if (activeTab === "quality") return (row.qualityDisagreement ? "DISAGREEMENT · " : "") + String(row.qualityLabel || row.qualityTier || "QUALITY").toUpperCase()
        if (activeTab === "exploration") return Boolean(row.executed) ? "EXECUTED · EPHEMERAL" : "EPHEMERAL"
        if (activeTab === "schedule") return Boolean(row.selected)
            ? (Boolean(row.deprioritized) ? "SELECTED · DEPRIORITIZED" : "SELECTED")
            : (Boolean(row.timeBudgetSkip) ? "TIME BUDGET SKIP" : "BUDGET SKIP")
        if (activeTab === "mentions") return String(row.mentionLabel || "CORROBORATING MENTION").toUpperCase()
        if (activeTab === "social") return String(row.contentType || "activity").replace(/_/g, " ").toUpperCase()
        if (activeTab === "triage") return String(row.triageLabel || row.triageStatus || "UNREVIEWED").replace(/_/g, " ").toUpperCase()
        if (activeTab === "correlation") return String(row.correlationLabel || "CORRELATION").toUpperCase()
        if (activeTab === "providers") return String(row.healthLabel || row.status || "provider").replace(/_/g, " ").toUpperCase()
        if (activeTab === "pivots") return Boolean(row.queued) ? "QUEUED" : "REVIEW"
        if (activeTab === "errors") return "ERROR"
        if (Boolean(row.sensitive)) return "SENSITIVE"
        if (Boolean(row.candidateOnly)) return "CANDIDATE"
        return String(row.status || row.type || "RESULT").replace(/_/g, " ").toUpperCase()
    }

    function rowMeta(row) {
        if (activeTab === "identity") {
            const score = Number(row.identityAlignmentScore || 0).toFixed(0)
            const sources = Number(row.corroborationCount || 0)
            return "Alignment " + score + (sources > 1 ? " · " + sources + " sources" : " · " + String(row.source || ""))
        }
        if (activeTab === "candidates") return String(row.source || "") + (row.meta ? " · " + String(row.meta) : "")
        if (activeTab === "possible") {
            const verification = row.accountVerificationStatus ? " · " + String(row.accountVerificationStatus).toUpperCase() : ""
            return String(row.source || "") + verification + " · visibility " + Number(row.visibilityScore || row.contextRelevanceScore || 0).toFixed(0) + (row.visibilityReason ? " · " + String(row.visibilityReason) : "")
        }
        if (activeTab === "accounts") {
            const httpText = row.accountVerificationHttpStatus ? " · HTTP " + String(row.accountVerificationHttpStatus) : ""
            return String(row.source || "") + httpText + (row.url ? " · " + String(row.url) : "")
        }
        if (activeTab === "quality") {
            return String(row.source || "")
                + " · Q " + Number(row.qualityScore || 0).toFixed(0)
                + " · relevance " + Number(row.qualityRelevanceScore || 0).toFixed(0)
                + " · pivot " + Number(row.qualityPivotScore || 0).toFixed(0)
                + " · persist " + Number(row.qualityPersistenceScore || 0).toFixed(0)
        }
        if (activeTab === "exploration") {
            return String(row.source || "quality")
                + " · D" + Number(row.depth || 0)
                + " · pivot " + Number(row.pivotScore || 0).toFixed(0)
                + " · persist " + Number(row.persistenceScore || 0).toFixed(0)
                + (row.parentSeedValue ? " · from " + String(row.parentSeedValue) : "")
        }
        if (activeTab === "schedule") {
            const estimate = Number(row.estimatedSeconds || 0)
            const risk = Number(row.timeoutRisk || 0)
            const health = String(row.healthState || "unknown")
            return "wave " + Number(row.wave || 0)
                + (row.source ? " · " + String(row.source) : "")
                + (row.capability ? " · " + String(row.capability) : "")
                + " · est " + estimate.toFixed(1) + "s"
                + " · health " + health.replace(/_/g, " ")
                + (risk > 0 ? " · timeout risk " + Math.round(risk * 100) + "%" : "")
        }
        if (activeTab === "mentions") {
            const mentionScore = Number(row.mentionScore || 0).toFixed(0)
            const sources = Number(row.corroborationCount || 0)
            return String(row.source || "") + " · mention " + mentionScore + (sources > 1 ? " · " + sources + " sources" : "")
        }
        if (activeTab === "social") {
            const signals = row.contextSignals || []
            return String(row.timestamp || "No timestamp")
                + (signals.length > 0 ? " · " + signals.slice(0, 3).join(" · ") : "")
                + (row.url ? " · " + String(row.url) : "")
        }
        if (activeTab === "triage") {
            return String(row.source || row.service || "")
                + " · score " + Number(row.triageScore || 0).toFixed(0)
                + (row.accountVerificationStatus ? " · " + String(row.accountVerificationStatus).toUpperCase() : "")
        }
        if (activeTab === "correlation") {
            const score = Number(row.correlationScore || 0).toFixed(0)
            const platforms = row.platforms || []
            return "Correlation " + score
                + (platforms.length > 0 ? " · " + platforms.join(" ↔ ") : "")
                + (row.leftPlatform ? " · " + String(row.leftPlatform) + " ↔ " + String(row.rightPlatform || "") : "")
        }
        if (activeTab === "providers") return String(row.records || 0) + " record(s) · D" + Number(row.depth || 0) + (row.healthState ? " · " + String(row.healthState).replace(/_/g, " ") : "")
        if (activeTab === "pivots") return (row.country ? String(row.country) + " · " : "") + "D" + Number(row.depth || 0)
        if (activeTab === "errors") return String(row.lane || "")
        const sourceText = String(row.source || "")
        const scoreText = row.score === undefined ? "" : (" · rank " + Number(row.score).toFixed(0))
        const contextText = row.contextRelevanceScore === undefined ? "" : (" · seed " + Number(row.contextRelevanceScore).toFixed(0))
        return sourceText + (row.meta ? " · " + String(row.meta) : "") + contextText + scoreText
    }

    function profilePayload() {
        return {
            firstName: firstName.text,
            middleName: middleName.text,
            lastName: lastName.text,
            birthDate: birthDate.text,
            aliases: aliases.text,
            usernames: usernames.text,
            emails: emails.text,
            phones: phones.text,
            country: country.text,
            region: region.text,
            city: city.text,
            postalCode: postalCode.text,
            address: address.text,
            organizations: organizations.text,
            registrationIds: registrationIds.text,
            vatIds: vatIds.text,
            leis: leis.text,
            domains: domains.text,
            urls: urls.text,
            ips: ips.text,
            asns: asns.text,
            hashes: hashes.text,
            orcids: orcids.text,
            npis: npis.text,
            cves: cves.text,
            dois: dois.text,
            caseNumbers: caseNumbers.text,
            cryptoAddresses: cryptoAddresses.text,
            repositories: repositories.text,
            keywords: keywords.text,
            notes: notes.text
        }
    }

    function optionPayload() {
        return {
            classic: classicCheck.checked,
            openWeb: webCheck.checked,
            federation: federationCheck.checked,
            registry: registryCheck.checked,
            followPivots: pivotCheck.checked,
            includeSensitiveNameRoutes: sensitiveCheck.checked
        }
    }

    function openMentionPersonDialog(row) {
        root.selectedMention = row || ({})
        root.mentionLinkError = ""
        root.mentionPersonOptions = investigationSearchBridge.personOptions(desktopBridge.currentCaseId)
        mentionPersonDialog.open()
    }

    function accountObservations(row) {
        const value = row || ({})
        const observations = value.accountObservations || []
        if (observations.length > 0) return observations
        return [{
            connector: value.source || "Unknown source",
            service: value.service || "",
            lane: value.lane || "",
            url: value.url || "",
            title: value.title || "",
            detail: value.detail || "",
            status: value.status || "",
            confidence: value.confidence,
            reliability: value.reliability,
            verificationStatus: value.accountVerificationStatus || "reported",
            verificationReason: value.accountVerificationReason || "",
            verificationChecked: Boolean(value.accountVerificationChecked),
            verificationHttpStatus: value.accountVerificationHttpStatus,
            verificationFinalUrl: value.accountVerificationFinalUrl || "",
            metadata: value.findingMetadata || ({})
        }]
    }

    function metadataText(value) {
        if (value === undefined || value === null) return "{}"
        try {
            return JSON.stringify(value, null, 2)
        } catch (error) {
            return String(value)
        }
    }

    function openAccountDetails(row) {
        root.selectedAccount = row || ({})
        root.accountEnrichmentCapability = investigationSearchBridge.accountEnrichmentCapability(root.selectedAccount)
        root.socialActivityCapability = investigationSearchBridge.socialActivityCapability(root.selectedAccount)
        investigationSearchBridge.clearAccountEnrichment()
        investigationSearchBridge.clearSocialActivity()
        accountDetailsDialog.open()
    }

    function accountEnrichmentMatchesSelectedAccount() {
        if (!root.accountEnrichment.hasRun) return false
        const selectedUrl = String(root.selectedAccount.url || "").replace(/\/$/, "").toLowerCase()
        const enrichmentUrl = String(root.accountEnrichment.profileUrl || "").replace(/\/$/, "").toLowerCase()
        if (selectedUrl.length > 0 && enrichmentUrl.length > 0) return selectedUrl === enrichmentUrl
        const selectedUsername = String(root.selectedAccount.seed || root.selectedAccount.title || "").replace(/^@/, "").toLowerCase()
        const enrichmentUsername = String(root.accountEnrichment.username || "").replace(/^@/, "").toLowerCase()
        return selectedUsername.length > 0 && selectedUsername === enrichmentUsername
    }

    component CompactMetric: Rectangle {
        id: compactMetric
        property string title: "Metric"
        property string value: "0"
        property string detail: ""
        property color accentColor: Theme.accent

        implicitHeight: 52
        radius: 8
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        Rectangle {
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 4
            height: 28
            radius: 2
            color: compactMetric.accentColor
        }

        Text {
            x: 26
            y: 8
            text: compactMetric.title
            color: Theme.textMuted
            font.pixelSize: 8
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }

        Text {
            x: 26
            y: 23
            text: compactMetric.value
            color: Theme.textPrimary
            font.pixelSize: 17
            font.weight: Font.DemiBold
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 72
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: compactMetric.detail
            color: Theme.textSecondary
            font.pixelSize: 9
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignRight
        }
    }

    opacity: 0
    Component.onCompleted: {
        root.reloadTargetPeople("")
        appear.start()
    }

    Connections {
        target: desktopBridge
        function onChanged() {
            if (root.visible)
                root.reloadTargetPeople("")
        }
    }
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
        anchors.topMargin: 16
        anchors.bottomMargin: 24
        spacing: 10

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 78

            Text {
                x: 1; y: 0
                text: "UNIFIED INVESTIGATION WORKSPACE"
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 1; y: 20
                text: "Investigation Search"
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Text {
                x: 2; y: 57
                text: "Enter everything already known. OSINTXZ builds a source plan, searches compatible layers and follows safe exact pivots."
                color: Theme.textSecondary
                font.pixelSize: 12
            }

            AppButton {
                id: runButton
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 180
                text: root.busy ? "Searching…" : "Run All Sources"
                primary: true
                enabled: root.workspaceMode === "investigation"
                    && desktopBridge.hasCurrentCase
                    && root.selectedTargetPersonId.length > 0
                    && !root.busy
                ToolTip.visible: hovered && !enabled
                ToolTip.delay: 400
                ToolTip.text: root.busy
                    ? "A search is already running."
                    : (!desktopBridge.hasCurrentCase
                        ? "Select an investigation first."
                        : (root.selectedTargetPersonId.length === 0
                            ? "Select or create the person these results belong to."
                            : ""))
                onClicked: {
                    root.activeTab = "results"
                    root.targetPersonError = ""
                    var started = investigationSearchBridge.search(
                        root.profilePayload(),
                        desktopBridge.currentCaseId,
                        root.optionPayload(),
                        root.selectedTargetPersonId
                    )
                    if (!started)
                        root.targetPersonError = investigationSearchBridge.message
                }
            }

            AppButton {
                anchors.right: runButton.left
                anchors.rightMargin: 10
                anchors.bottom: parent.bottom
                width: 92
                text: "Clear"
                quiet: true
                enabled: !root.busy
                onClicked: investigationSearchBridge.clear()
            }
        }

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            spacing: 6

            Repeater {
                model: [
                    { key: "investigation", label: "All-Source Investigation" },
                    { key: "stored", label: "Stored Intelligence" }
                ]
                delegate: Rectangle {
                    id: modeButton
                    required property var modelData
                    property bool selected: root.workspaceMode === String(modelData.key)
                    width: modeLabel.implicitWidth + 26
                    height: 30
                    radius: 7
                    color: selected ? Theme.accentSoft : (modeMouse.containsMouse ? Theme.surfaceHover : "transparent")
                    border.width: 1
                    border.color: selected ? Theme.accent : Theme.border
                    Text {
                        id: modeLabel
                        anchors.centerIn: parent
                        text: String(modeButton.modelData.label)
                        color: modeButton.selected ? Theme.textPrimary : Theme.textSecondary
                        font.pixelSize: 10
                        font.weight: modeButton.selected ? Font.DemiBold : Font.Normal
                    }
                    MouseArea {
                        id: modeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.workspaceMode = String(modeButton.modelData.key)
                    }
                }
            }
        }

        RowLayout {
            visible: root.workspaceMode === "investigation"
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 52 : 0
            spacing: 8

            CompactMetric {
                Layout.fillWidth: true
                title: "Known Seeds"
                value: String(root.summary.seeds || 0)
                detail: root.runData.hasRun ? "current search" : "ready"
                accentColor: Theme.accent
            }
            CompactMetric {
                Layout.fillWidth: true
                title: "Results"
                value: String(root.summary.results || 0)
                detail: String(root.summary.evidenceCreated || 0) + " saved"
                accentColor: Theme.success
            }
            CompactMetric {
                Layout.fillWidth: true
                title: "Identity Leads"
                value: String(root.summary.identityCandidates || 0)
                detail: String(Number(root.summary.identityStrong || 0) + Number(root.summary.identitySupported || 0)) + " supported"
                accentColor: (Number(root.summary.identityStrong || 0) + Number(root.summary.identitySupported || 0)) > 0
                    ? Theme.success
                    : Theme.warning
            }
            CompactMetric {
                Layout.fillWidth: true
                title: "New Pivots"
                value: String(root.summary.pivots || 0)
                detail: pivotCheck.checked ? "auto follow on" : "auto follow off"
                accentColor: Theme.warning
            }
        }

        RowLayout {
            visible: root.workspaceMode === "investigation"
            Layout.fillWidth: true
            Layout.fillHeight: visible
            spacing: Spacing.panelGap

            Panel {
                Layout.preferredWidth: 515
                Layout.minimumWidth: 450
                Layout.maximumWidth: 560
                Layout.fillHeight: true
                title: "Known Data"
                subtitle: desktopBridge.hasCurrentCase
                    ? (root.selectedTargetPersonId.length
                        ? ("Search target → " + root.selectedTargetPersonLabel())
                        : "Choose which person will receive persisted results")
                    : "Select an investigation before running"
                iconSource: "../../assets/icons/users_cyan.svg"

                Flickable {
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: formColumn.height + 24
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: formColumn
                        x: 14
                        width: parent.width - 28
                        spacing: 8

                        Text { text: "SEARCH TARGET"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }

                        RowLayout {
                            width: parent.width
                            spacing: 8

                            AppComboBox {
                                id: targetPersonBox
                                Layout.fillWidth: true
                                model: root.targetPersonOptions
                                textRole: "label"
                                onCurrentIndexChanged: {
                                    var item = currentIndex >= 0 && currentIndex < root.targetPersonOptions.length
                                        ? root.targetPersonOptions[currentIndex]
                                        : null
                                    root.selectedTargetPersonId = item
                                        ? String(item.id || "")
                                        : ""
                                    root.targetPersonError = ""
                                }
                            }

                            AppButton {
                                text: "+ New Person"
                                Layout.preferredWidth: 124
                                enabled: desktopBridge.hasCurrentCase && !root.busy
                                onClicked: {
                                    newSearchPersonName.text = root.suggestedPersonName()
                                    newSearchPersonDescription.text = ""
                                    newSearchPersonError.text = ""
                                    newSearchPersonDialog.open()
                                    newSearchPersonName.forceActiveFocus()
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            text: root.selectedTargetPersonId.length
                                ? "Persisted search results will be attributed to this PERSON. This is context, not automatic identity confirmation."
                                : "Select an existing PERSON or create a new one before running the search."
                            color: root.selectedTargetPersonId.length ? Theme.textSecondary : Theme.warning
                            font.pixelSize: 8
                            wrapMode: Text.Wrap
                        }

                        Text {
                            width: parent.width
                            visible: root.targetPersonError.length > 0
                            text: root.targetPersonError
                            color: Theme.danger
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Text { text: "IDENTITY"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8
                            AppTextField { id: firstName; Layout.fillWidth: true; placeholderText: "First name" }
                            AppTextField { id: lastName; Layout.fillWidth: true; placeholderText: "Last name" }
                            AppTextField { id: middleName; Layout.fillWidth: true; placeholderText: "Middle name" }
                            AppTextField { id: birthDate; Layout.fillWidth: true; placeholderText: "Birth date · YYYY-MM-DD" }
                        }
                        AppTextArea { id: aliases; width: parent.width; height: 58; placeholderText: "Aliases / alternative names · one per line" }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }
                        Text { text: "ONLINE IDENTITIES"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8
                            AppTextArea { id: usernames; Layout.fillWidth: true; height: 66; placeholderText: "Usernames" }
                            AppTextArea { id: emails; Layout.fillWidth: true; height: 66; placeholderText: "Emails" }
                            AppTextArea { id: phones; Layout.fillWidth: true; height: 66; placeholderText: "Phones" }
                            AppTextArea { id: repositories; Layout.fillWidth: true; height: 66; placeholderText: "Repositories · owner/repo" }
                        }

                        Rectangle {
                            width: parent.width
                            height: 42
                            radius: 7
                            color: advancedFieldsMouse.containsMouse ? Theme.surfaceHover : "transparent"
                            border.width: 1
                            border.color: Theme.divider

                            Text {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: "ADDITIONAL IDENTIFIERS"
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.0
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.advancedFieldsOpen ? "Hide  ▲" : "Location · organizations · technical  ▼"
                                color: Theme.textMuted
                                font.pixelSize: 9
                            }
                            MouseArea {
                                id: advancedFieldsMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.advancedFieldsOpen = !root.advancedFieldsOpen
                            }
                        }

                        Column {
                            width: parent.width
                            visible: root.advancedFieldsOpen
                            spacing: 8

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }
                        Text { text: "LOCATION"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8
                            AppTextField { id: country; Layout.fillWidth: true; placeholderText: "Country · ISO-2 (UA, US, GB…)" }
                            AppTextField { id: region; Layout.fillWidth: true; placeholderText: "Region / state" }
                            AppTextField { id: city; Layout.fillWidth: true; placeholderText: "City" }
                            AppTextField { id: postalCode; Layout.fillWidth: true; placeholderText: "Postal code" }
                        }
                        AppTextField { id: address; width: parent.width; placeholderText: "Street / address" }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }
                        Text { text: "ORGANIZATIONS & REGISTRIES"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8
                            AppTextArea { id: organizations; Layout.fillWidth: true; height: 66; placeholderText: "Organizations / employers" }
                            AppTextArea { id: registrationIds; Layout.fillWidth: true; height: 66; placeholderText: "Registration IDs / UEI / DUNS" }
                            AppTextArea { id: vatIds; Layout.fillWidth: true; height: 66; placeholderText: "VAT IDs" }
                            AppTextArea { id: leis; Layout.fillWidth: true; height: 66; placeholderText: "LEIs" }
                            AppTextArea { id: caseNumbers; Layout.fillWidth: true; height: 66; placeholderText: "Court case numbers" }
                            AppTextArea { id: orcids; Layout.fillWidth: true; height: 66; placeholderText: "ORCID IDs" }
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }
                        Text { text: "WEB / NETWORK / TECHNICAL"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8
                            AppTextArea { id: domains; Layout.fillWidth: true; height: 66; placeholderText: "Domains" }
                            AppTextArea { id: urls; Layout.fillWidth: true; height: 66; placeholderText: "URLs" }
                            AppTextArea { id: ips; Layout.fillWidth: true; height: 66; placeholderText: "IP addresses" }
                            AppTextArea { id: asns; Layout.fillWidth: true; height: 66; placeholderText: "ASNs" }
                            AppTextArea { id: hashes; Layout.fillWidth: true; height: 66; placeholderText: "File hashes" }
                            AppTextArea { id: cves; Layout.fillWidth: true; height: 66; placeholderText: "CVE IDs" }
                            AppTextArea { id: dois; Layout.fillWidth: true; height: 66; placeholderText: "DOIs" }
                            AppTextArea { id: npis; Layout.fillWidth: true; height: 66; placeholderText: "NPI IDs" }
                            AppTextArea { id: cryptoAddresses; Layout.fillWidth: true; height: 66; placeholderText: "Crypto addresses" }
                            AppTextArea { id: keywords; Layout.fillWidth: true; height: 66; placeholderText: "Keywords / context terms" }
                        }


                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Rectangle {
                            width: parent.width
                            height: 42
                            radius: 7
                            color: searchPolicyMouse.containsMouse ? Theme.surfaceHover : "transparent"
                            border.width: 1
                            border.color: Theme.divider

                            Text {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: "SEARCH POLICY"
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.0
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.searchPolicyOpen ? "Hide options  ▲" : "Automatic · all standard layers  ▼"
                                color: Theme.textMuted
                                font.pixelSize: 9
                            }
                            MouseArea {
                                id: searchPolicyMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.searchPolicyOpen = !root.searchPolicyOpen
                            }
                        }

                        Column {
                            width: parent.width
                            visible: root.searchPolicyOpen
                            spacing: 2

                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 6
                            rowSpacing: 0
                            CheckBox { id: classicCheck; text: "Classic OSINT"; checked: true }
                            CheckBox { id: webCheck; text: "Open-Web / archives"; checked: true }
                            CheckBox { id: federationCheck; text: "Federation sources"; checked: true }
                            CheckBox { id: registryCheck; text: "Registries"; checked: true }
                            CheckBox { id: pivotCheck; text: "Follow safe exact pivots"; checked: true; Layout.columnSpan: 2 }
                            CheckBox { id: sensitiveCheck; text: "Include sensitive legal name routes"; checked: false; Layout.columnSpan: 2 }
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.Wrap
                            text: "Sensitive legal name search is opt-in. A court/wanted/sanctions-like name match never establishes identity, guilt or conviction. Contract, verified-scope and dark-web sources stay explicit-only."
                            color: Theme.textMuted
                            font.pixelSize: 9
                        }

                        }

                        AppTextArea { id: notes; width: parent.width; height: 68; placeholderText: "Analyst notes / context (not automatically treated as identifiers)" }

                        Item { width: 1; height: 10 }
                    }

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "All-Source Result Center"
                subtitle: root.runData.hasRun
                    ? (String(root.runData.status || "").replace(/_/g, " ") + " · " + String(root.runData.durationText || ""))
                    : "No investigation search in this session"
                iconSource: "../../assets/icons/globe_blue.svg"

                Item {
                    anchors.fill: parent

                    Item {
                        id: progressStrip
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 54

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 32
                            text: root.busy
                                ? String(root.runData.progressText || "Searching…")
                                : root.runData.hasRun
                                    ? (String(root.summary.results || 0) + " relevant · " + String(root.summary.possible || 0) + " possible · " + String(root.summary.rawResults || root.summary.results || 0) + " raw · " + String(root.summary.lowValueSuppressed || 0) + " suppressed · " + String(root.summary.missedDueToBudget || 0) + " budget-skipped" + (Number(root.summary.skippedDueToTimeBudget || 0) > 0 ? " · " + String(root.summary.skippedDueToTimeBudget) + " time-skipped" : ""))
                                    : "Fill any known fields and run all compatible source layers."
                            color: root.busy ? Theme.accent : Theme.textSecondary
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                    }

                    Item {
                        id: tabs
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: progressStrip.bottom
                        height: 78

                        Row {
                            id: resultSectionRow
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.top: parent.top
                            anchors.topMargin: 6
                            height: 30
                            spacing: 6

                            Repeater {
                                model: [
                                    { key: "results", label: "Results" },
                                    { key: "review", label: "Review" },
                                    { key: "activity", label: "Activity" }
                                ]
                                delegate: Rectangle {
                                    id: sectionButton
                                    required property var modelData
                                    property bool selected: root.resultSectionForTab(root.activeTab) === String(modelData.key)
                                    width: Math.max(88, sectionText.implicitWidth + 26)
                                    height: 30
                                    radius: 7
                                    color: selected ? Theme.accentSoft : (sectionMouse.containsMouse ? Theme.surfaceHover : "transparent")
                                    border.width: 1
                                    border.color: selected ? Theme.accent : "transparent"

                                    Text {
                                        id: sectionText
                                        anchors.centerIn: parent
                                        text: String(sectionButton.modelData.label)
                                            + "  " + root.sectionCount(String(sectionButton.modelData.key))
                                        color: sectionButton.selected ? Theme.textPrimary : Theme.textSecondary
                                        font.pixelSize: 10
                                        font.weight: sectionButton.selected ? Font.DemiBold : Font.Medium
                                    }

                                    MouseArea {
                                        id: sectionMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.activeTab = root.sectionDefaultTab(String(sectionButton.modelData.key))
                                    }
                                }
                            }
                        }

                        Row {
                            id: resultSubTabsRow
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.right: resultModeRow.visible ? resultModeRow.left : parent.right
                            anchors.rightMargin: 10
                            anchors.top: resultSectionRow.bottom
                            anchors.topMargin: 5
                            height: 28
                            spacing: 5
                            clip: true

                            Repeater {
                                model: root.sectionTabs(root.resultSectionForTab(root.activeTab))
                                delegate: Rectangle {
                                    id: subTabButton
                                    required property var modelData
                                    property bool selected: root.activeTab === String(modelData.key)
                                    width: subTabText.implicitWidth + 20
                                    height: 26
                                    radius: 6
                                    color: selected ? Theme.surfaceRaised : (subTabMouse.containsMouse ? Theme.surfaceHover : "transparent")

                                    Text {
                                        id: subTabText
                                        anchors.centerIn: parent
                                        text: String(subTabButton.modelData.label)
                                            + "  " + root.itemCount(String(subTabButton.modelData.key))
                                        color: subTabButton.selected ? Theme.textPrimary : Theme.textMuted
                                        font.pixelSize: 9
                                        font.weight: subTabButton.selected ? Font.DemiBold : Font.Normal
                                    }

                                    MouseArea {
                                        id: subTabMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.activeTab = String(subTabButton.modelData.key)
                                    }
                                }
                            }
                        }

                        Row {
                            id: resultModeRow
                            visible: root.activeTab === "results" && root.runData.hasRun
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.top: resultSectionRow.bottom
                            anchors.topMargin: 5
                            height: 28
                            spacing: 5

                            Repeater {
                                model: [
                                    { key: "clean", label: "Clean" },
                                    { key: "raw", label: "Raw" }
                                ]
                                delegate: Rectangle {
                                    id: resultModeButton
                                    required property var modelData
                                    property bool selected: root.resultViewMode === String(modelData.key)
                                    width: resultModeText.implicitWidth + 20
                                    height: 26
                                    radius: 6
                                    color: selected ? Theme.accentSoft : (resultModeMouse.containsMouse ? Theme.surfaceHover : "transparent")
                                    border.width: 1
                                    border.color: selected ? Theme.accent : Theme.border
                                    Text {
                                        id: resultModeText
                                        anchors.centerIn: parent
                                        text: String(resultModeButton.modelData.label)
                                        color: resultModeButton.selected ? Theme.textPrimary : Theme.textMuted
                                        font.pixelSize: 9
                                        font.weight: resultModeButton.selected ? Font.DemiBold : Font.Normal
                                    }
                                    MouseArea {
                                        id: resultModeMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.resultViewMode = String(resultModeButton.modelData.key)
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
                        id: resultList
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: tabs.bottom
                        anchors.bottom: policyBar.top
                        clip: true
                        spacing: 0
                        model: root.tabItems()
                        cacheBuffer: 500
                        reuseItems: true
                        visible: !root.busy && count > 0

                        delegate: Rectangle {
                            id: row
                            required property var modelData
                            property string titleText: root.rowTitle(row.modelData)
                            property string detailText: root.rowDetail(row.modelData)
                            property string metaText: root.rowMeta(row.modelData)
                            property bool needsExtraLine: detailText.length > 105 || metaText.length > 120 || titleText.length > 105
                            property int rightColumnWidth: Math.min(196, Math.max(132, width * 0.24))
                            property int leftTextWidth: Math.max(150, width - 30 - rightColumnWidth - 30)

                            width: resultList.width
                            height: needsExtraLine ? 106 : 86
                            color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"

                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                            Rectangle {
                                x: 16
                                anchors.verticalCenter: parent.verticalCenter
                                width: 4
                                height: Math.max(44, parent.height - 30)
                                radius: 2
                                color: root.activeTab === "errors"
                                    ? Theme.danger
                                    : root.activeTab === "quality"
                                        ? root.statusColor(row.modelData.qualityTier === "noise" ? "failed" : (row.modelData.qualityTier === "possible" ? "possible" : "success"))
                                        : root.activeTab === "exploration"
                                            ? root.statusColor(row.modelData.executed ? "success" : "possible")
                                        : root.activeTab === "schedule"
                                            ? root.statusColor(row.modelData.selected ? "success" : "possible")
                                        : root.activeTab === "accounts"
                                            ? root.statusColor(row.modelData.accountVerificationStatus || "reported")
                                            : root.statusColor(root.activeTab === "identity" ? row.modelData.identityStatus : (row.modelData.status || (row.modelData.queued ? "success" : "candidate")))
                            }

                            Text {
                                x: 30
                                y: 10
                                width: row.leftTextWidth
                                height: 19
                                text: row.titleText
                                color: Theme.textPrimary
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                            Text {
                                x: 30
                                y: 33
                                width: row.leftTextWidth
                                height: row.needsExtraLine ? 36 : 19
                                text: row.detailText
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                                maximumLineCount: row.needsExtraLine ? 2 : 1
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignTop
                            }
                            Text {
                                x: 30
                                y: row.needsExtraLine ? 76 : 60
                                width: row.leftTextWidth
                                height: 17
                                text: row.metaText
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }

                            Rectangle {
                                id: statusBadge
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: parent.top
                                anchors.topMargin: 12
                                width: Math.min(row.rightColumnWidth - 12, Math.max(72, badge.implicitWidth + 18))
                                height: 24
                                radius: 6
                                color: "transparent"
                                border.width: 1
                                border.color: root.activeTab === "quality"
                                    ? root.statusColor(row.modelData.qualityTier === "noise" ? "failed" : (row.modelData.qualityTier === "possible" ? "possible" : "success"))
                                    : root.activeTab === "exploration"
                                        ? root.statusColor(row.modelData.executed ? "success" : "possible")
                                    : root.activeTab === "schedule"
                                        ? root.statusColor(row.modelData.selected ? "success" : "possible")
                                    : root.activeTab === "accounts"
                                        ? root.statusColor(row.modelData.accountVerificationStatus || "reported")
                                        : root.statusColor(root.activeTab === "identity" ? row.modelData.identityStatus : (row.modelData.status || (row.modelData.queued ? "success" : "candidate")))
                                Text {
                                    id: badge
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    text: root.rowBadge(row.modelData)
                                    color: parent.border.color
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.35
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                            }
                            Text {
                                visible: root.activeTab !== "mentions"
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: statusBadge.bottom
                                anchors.topMargin: 10
                                width: row.rightColumnWidth - 12
                                height: row.needsExtraLine ? 38 : 30
                                horizontalAlignment: Text.AlignRight
                                verticalAlignment: Text.AlignTop
                                text: root.activeTab === "errors" && Number(row.modelData.attempts || 1) > 1
                                    ? (String(row.modelData.lane || "") + " · " + Number(row.modelData.attempts) + " attempts")
                                    : String(row.modelData.lane || "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                            AppButton {
                                id: addMentionToPersonButton
                                visible: root.activeTab === "mentions"
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: statusBadge.bottom
                                anchors.topMargin: 8
                                width: Math.min(126, row.rightColumnWidth - 8)
                                height: 30
                                text: "Add to person"
                                primary: true
                                onClicked: root.openMentionPersonDialog(row.modelData)
                            }
                            MouseArea {
                                id: rowMouse
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.right: addMentionToPersonButton.visible ? addMentionToPersonButton.left : parent.right
                                hoverEnabled: true
                                cursorShape: (root.activeTab === "accounts" || row.modelData.url) ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (root.activeTab === "accounts") {
                                        root.openAccountDetails(row.modelData)
                                    } else if (row.modelData.url) {
                                        desktopBridge.openExternalUrl(String(row.modelData.url))
                                    }
                                }
                            }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    EmptyState {
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: tabs.bottom; anchors.bottom: policyBar.top
                        anchors.margins: 18
                        visible: root.busy
                        iconSource: "../../assets/icons/globe_blue.svg"
                        title: "Searching source layers"
                        description: String(root.runData.progressText || "Building and executing a bounded search plan…")
                    }
                    EmptyState {
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.top: tabs.bottom; anchors.bottom: policyBar.top
                        anchors.margins: 18
                        visible: !root.busy && resultList.count === 0
                        iconSource: "../../assets/icons/search.svg"
                        title: root.runData.hasRun ? "No items in this view" : "Ready for an all-source investigation"
                        description: root.runData.hasRun
                            ? (root.activeTab === "results" && root.resultViewMode === "clean"
                                ? "No useful consolidated results remain. Switch to Raw to inspect the complete provider stream."
                                : root.activeTab === "possible"
                                    ? "No medium-confidence results need review. Strict identifiers remain strict; weak noise stays in Raw."
                                : root.activeTab === "quality"
                                    ? "No shadow quality observations are available for this run."
                                : root.activeTab === "exploration"
                                    ? "No quality-approved ephemeral pivots were created for this run."
                                : root.activeTab === "schedule"
                                    ? "No retrieval scheduling decisions are available for this run."
                                : root.activeTab === "identity"
                                    ? "No person-like records contained enough structured identity signals to score."
                                    : root.activeTab === "candidates"
                                        ? "No review-only candidates survived the strict seed relevance gate."
                                        : root.activeTab === "mentions"
                                            ? "No source contained enough independent matching signals to qualify as a corroborating mention."
                                            : "Switch result tabs or adjust the known data and source policy.")
                            : "Known values are routed independently. Weak name matches stay candidates; exact identifiers may become bounded pivots."
                    }

                    Rectangle {
                        id: policyBar
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 62
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 28
                            wrapMode: Text.Wrap
                            text: desktopBridge.hasCurrentCase
                                ? ("Case: " + desktopBridge.currentCaseTitle + " · Identity alignment is an explainable relevance score, not proof that records belong to the same person. Review-only candidates and multi-signal Mentions are separated from Results; pre-persistence relevance gates protect Evidence/Entities. Raw secret values are never stored.")
                                : "Select an investigation before running."
                            color: Theme.textMuted
                            font.pixelSize: 9
                        }
                    }
                }
            }
        }

        Panel {
            visible: root.workspaceMode === "stored"
            Layout.fillWidth: true
            Layout.fillHeight: visible
            title: "Stored Intelligence"
            subtitle: desktopBridge.currentCaseTitle
                ? ("Search persisted data in " + desktopBridge.currentCaseTitle)
                : "Search persisted data across investigations"
            iconSource: "../../assets/icons/search.svg"

            Item {
                anchors.fill: parent

                AppTextField {
                    id: storedQuery
                    anchors.left: parent.left
                    anchors.right: storedButton.left
                    anchors.top: parent.top
                    anchors.leftMargin: 16
                    anchors.rightMargin: 10
                    anchors.topMargin: 14
                    placeholderText: "Search already stored entities, evidence and indexed intelligence…"
                    Keys.onReturnPressed: root.storedResults = desktopBridge.search(text)
                }
                AppButton {
                    id: storedButton
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: 16
                    anchors.topMargin: 14
                    width: 105
                    text: "Search"
                    primary: true
                    onClicked: root.storedResults = desktopBridge.search(storedQuery.text)
                }

                ListView {
                    id: storedList
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: storedQuery.bottom
                    anchors.bottom: parent.bottom
                    anchors.topMargin: 14
                    clip: true
                    model: root.storedResults
                    delegate: Rectangle {
                        id: storedRow
                        required property var modelData
                        width: storedList.width
                        height: 72
                        color: "transparent"
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        Text { x: 18; y: 14; width: parent.width - 180; text: String(storedRow.modelData.title || "Stored result"); color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                        Text { x: 18; y: 39; width: parent.width - 180; text: String(storedRow.modelData.detail || ""); color: Theme.textMuted; font.pixelSize: 10; elide: Text.ElideRight }
                        Text { anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter; text: String(storedRow.modelData.status || ""); color: Theme.accent; font.pixelSize: 10 }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }

                EmptyState {
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.top: storedQuery.bottom; anchors.bottom: parent.bottom
                    anchors.margins: 18
                    visible: storedList.count === 0
                    iconSource: "../../assets/icons/search.svg"
                    title: "Search persisted intelligence"
                    description: "This is the previous local unified-search capability, now kept beside the new live all-source workflow."
                }
            }
        }
    }

    Dialog {
        id: accountDetailsDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(760, root.width - 80)
        height: Math.min(650, root.height - 70)
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 88
                color: "transparent"
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                Text {
                    x: 20; y: 13
                    width: Math.max(150, parent.width - 510)
                    text: String(root.selectedAccount.title || root.selectedAccount.value || "Account details")
                    color: Theme.textPrimary
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    x: 20; y: 43
                    width: Math.max(150, parent.width - 510)
                    text: String(root.selectedAccount.url || root.selectedAccount.meta || "")
                    color: Theme.textMuted
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
                AppButton {
                    id: collectActivityButton
                    anchors.right: deepEnrichAccountButton.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 126
                    text: root.socialActivityBusy
                        ? "Collecting…"
                        : (root.socialActivityCapability.available ? "Collect activity" : "No activity API")
                    primary: root.socialActivityCapability.available
                    enabled: root.socialActivityCapability.available
                        && !root.socialActivityBusy
                        && !root.accountEnrichmentBusy
                    ToolTip.visible: hovered && !root.socialActivityCapability.available
                    ToolTip.delay: 250
                    ToolTip.text: String(root.socialActivityCapability.reason || "Public activity collection is unavailable for this platform.")
                    onClicked: investigationSearchBridge.collectPublicActivity(root.selectedAccount)
                }
                AppButton {
                    id: deepEnrichAccountButton
                    anchors.right: openAccountProfileButton.visible ? openAccountProfileButton.left : closeAccountDetailsButton.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 122
                    text: root.accountEnrichmentBusy
                        ? "Enriching…"
                        : (root.accountEnrichmentCapability.available ? "Deep enrich" : "Unavailable")
                    primary: root.accountEnrichmentCapability.available
                    enabled: root.accountEnrichmentCapability.available && !root.accountEnrichmentBusy && !root.socialActivityBusy
                    ToolTip.visible: hovered && !root.accountEnrichmentCapability.available
                    ToolTip.delay: 250
                    ToolTip.text: String(root.accountEnrichmentCapability.reason || "Maigret deep enrichment is unavailable for this platform.")
                    onClicked: investigationSearchBridge.deepEnrichAccount(root.selectedAccount)
                }
                AppButton {
                    id: openAccountProfileButton
                    visible: Boolean(root.selectedAccount.url)
                    anchors.right: closeAccountDetailsButton.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 108
                    text: "Open profile"
                    onClicked: desktopBridge.openExternalUrl(String(root.selectedAccount.url || ""))
                }
                AppButton {
                    id: closeAccountDetailsButton
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    width: 78
                    text: "Close"
                    onClicked: accountDetailsDialog.close()
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: accountDetailsColumn.height + 28
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                Column {
                    id: accountDetailsColumn
                    x: 20
                    y: 16
                    width: parent.width - 40
                    spacing: 12

                    RowLayout {
                        width: parent.width
                        spacing: 12
                        Text {
                            Layout.fillWidth: true
                            text: "ACCOUNT SIGNAL"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.1
                        }
                        Text {
                            text: String(Number(root.selectedAccount.corroborationCount || 1)) + " source(s)"
                            color: Theme.accent
                            font.pixelSize: 9
                        }
                    }

                    Text {
                        width: parent.width
                        text: "Seed: " + String(root.selectedAccount.seed || "")
                            + (root.selectedAccount.service ? " · Platform: " + String(root.selectedAccount.service) : "")
                            + (root.selectedAccount.score !== undefined ? " · Rank: " + Number(root.selectedAccount.score).toFixed(0) : "")
                        color: Theme.textSecondary
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                    }

                    Rectangle {
                        width: parent.width
                        height: accountVerificationText.contentHeight + 30
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: root.statusColor(root.selectedAccount.accountVerificationStatus || "reported")

                        Text {
                            id: accountVerificationBadge
                            x: 12
                            y: 8
                            text: String(root.selectedAccount.accountVerificationStatus || "reported").replace(/_/g, " ").toUpperCase()
                            color: parent.border.color
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }
                        Text {
                            id: accountVerificationText
                            x: 12
                            y: 26
                            width: parent.width - 24
                            text: String(root.selectedAccount.accountVerificationReason || "Provider-reported account has not been independently verified.")
                                + (root.selectedAccount.accountVerificationHttpStatus ? " · HTTP " + String(root.selectedAccount.accountVerificationHttpStatus) : "")
                                + (root.selectedAccount.accountVerificationFinalUrl && root.selectedAccount.accountVerificationFinalUrl !== root.selectedAccount.url
                                    ? " · Final URL: " + String(root.selectedAccount.accountVerificationFinalUrl) : "")
                                + (root.selectedAccount.accountBrowserVerificationChecked
                                    ? " · Browser checked" : "")
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }
                    }

                    Rectangle {
                        visible: Boolean(root.selectedAccount.accountBrowserVerificationStatus)
                        width: parent.width
                        height: browserVerificationColumn.height + 24
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider

                        Column {
                            id: browserVerificationColumn
                            x: 12
                            y: 12
                            width: parent.width - 24
                            spacing: 5

                            Text {
                                width: parent.width
                                text: "BROWSER VERIFICATION · "
                                    + String(root.selectedAccount.accountBrowserVerificationStatus || "").toUpperCase()
                                color: root.statusColor(root.selectedAccount.accountBrowserVerificationStatus || "uncertain")
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                text: String(root.selectedAccount.accountBrowserVerificationReason || "")
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Text {
                                visible: (root.selectedAccount.accountBrowserVerificationEvidenceSignals || []).length > 0
                                width: parent.width
                                text: "Signals: " + (root.selectedAccount.accountBrowserVerificationEvidenceSignals || []).join(" · ")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Text {
                                visible: Boolean(root.selectedAccount.accountBrowserVerificationTitle)
                                width: parent.width
                                text: "Rendered title: " + String(root.selectedAccount.accountBrowserVerificationTitle || "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Rectangle {
                        visible: Boolean(root.socialActivity.hasRun)
                        width: parent.width
                        height: socialActivityColumn.height + 24
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider

                        Column {
                            id: socialActivityColumn
                            x: 12
                            y: 12
                            width: parent.width - 24
                            spacing: 6

                            Text {
                                width: parent.width
                                text: "PUBLIC ACTIVITY · "
                                    + String(root.socialActivity.status || "unknown").replace(/_/g, " ").toUpperCase()
                                color: root.statusColor(root.socialActivity.status || "reported")
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                text: String(root.socialActivity.platform || "")
                                    + (root.socialActivity.username ? " · @" + String(root.socialActivity.username) : "")
                                    + " · " + Number(root.socialActivity.count || 0) + " item(s)"
                                    + ((root.socialActivity.persistence || {}).created !== undefined
                                        ? " · " + Number((root.socialActivity.persistence || {}).created || 0) + " new evidence" : "")
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Text {
                                visible: Boolean(root.socialActivity.error)
                                width: parent.width
                                text: String(root.socialActivity.error || "")
                                color: Theme.danger
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Repeater {
                                model: (root.socialActivity.items || []).slice(0, 8)
                                delegate: Rectangle {
                                    required property var modelData
                                    width: socialActivityColumn.width
                                    height: activityText.contentHeight + 28
                                    radius: 7
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.divider

                                    Text {
                                        id: activityText
                                        x: 10
                                        y: 10
                                        width: parent.width - 20
                                        text: String(modelData.contentType || "activity").toUpperCase()
                                            + " · " + String(modelData.timestamp || "")
                                            + "\n" + String(modelData.text || "")
                                        color: Theme.textSecondary
                                        font.pixelSize: 9
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }
                    }

                    Repeater {
                        model: root.accountObservations(root.selectedAccount)
                        delegate: Rectangle {
                            id: observationCard
                            required property var modelData
                            width: accountDetailsColumn.width
                            height: observationContent.height + 28
                            radius: 9
                            color: Theme.surfaceHover
                            border.width: 1
                            border.color: Theme.divider

                            Column {
                                id: observationContent
                                x: 14
                                y: 14
                                width: parent.width - 28
                                spacing: 7

                                Text {
                                    width: parent.width
                                    text: String(observationCard.modelData.connector || "Unknown source")
                                        + (observationCard.modelData.service ? " · " + String(observationCard.modelData.service) : "")
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: (observationCard.modelData.confidence !== undefined && observationCard.modelData.confidence !== null
                                        ? "Confidence " + Number(observationCard.modelData.confidence).toFixed(2) : "Confidence n/a")
                                        + " · "
                                        + (observationCard.modelData.reliability !== undefined && observationCard.modelData.reliability !== null
                                            ? "Reliability " + Number(observationCard.modelData.reliability).toFixed(2) : "Reliability n/a")
                                        + (observationCard.modelData.status ? " · " + String(observationCard.modelData.status) : "")
                                    color: Theme.textMuted
                                    font.pixelSize: 9
                                }
                                Text {
                                    visible: Boolean(observationCard.modelData.verificationStatus)
                                    width: parent.width
                                    text: "Validation: " + String(observationCard.modelData.verificationStatus || "reported").toUpperCase()
                                        + (observationCard.modelData.verificationHttpStatus ? " · HTTP " + String(observationCard.modelData.verificationHttpStatus) : "")
                                        + (observationCard.modelData.verificationReason ? " · " + String(observationCard.modelData.verificationReason) : "")
                                    color: root.statusColor(observationCard.modelData.verificationStatus || "reported")
                                    font.pixelSize: 9
                                    wrapMode: Text.Wrap
                                }
                                Text {
                                    visible: Boolean(observationCard.modelData.url)
                                    width: parent.width
                                    text: String(observationCard.modelData.url || "")
                                    color: Theme.accent
                                    font.pixelSize: 9
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: "PROVIDER METADATA"
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                }
                                Rectangle {
                                    width: parent.width
                                    height: Math.max(74, metadataTextItem.contentHeight + 20)
                                    radius: 7
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.divider
                                    TextEdit {
                                        id: metadataTextItem
                                        x: 10
                                        y: 10
                                        width: parent.width - 20
                                        text: root.metadataText(observationCard.modelData.metadata || ({}))
                                        color: Theme.textSecondary
                                        font.pixelSize: 9
                                        font.family: "Consolas"
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: TextEdit.WrapAnywhere
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.divider
                    }

                    RowLayout {
                        width: parent.width
                        spacing: 8
                        Text {
                            Layout.fillWidth: true
                            text: "DEEP ENRICHMENT"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.1
                        }
                        Text {
                            visible: root.accountEnrichmentMatchesSelectedAccount()
                            text: root.accountEnrichmentBusy
                                ? "RUNNING"
                                : String(root.accountEnrichment.status || "UNKNOWN").toUpperCase()
                            color: root.accountEnrichmentBusy
                                ? Theme.warning
                                : root.statusColor(root.accountEnrichment.status)
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }
                    }

                    Rectangle {
                        visible: !root.accountEnrichmentCapability.available && !root.accountEnrichmentBusy
                        width: parent.width
                        height: unavailableEnrichmentText.contentHeight + 24
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider
                        Text {
                            id: unavailableEnrichmentText
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            text: String(root.accountEnrichmentCapability.reason || "Maigret deep enrichment is unavailable for this platform.")
                            color: Theme.textMuted
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }
                    }


                    Rectangle {
                        visible: root.accountEnrichmentBusy && root.accountEnrichmentMatchesSelectedAccount()
                        width: parent.width
                        height: 62
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider
                        Text {
                            anchors.fill: parent
                            anchors.margins: 12
                            text: "Maigret is parsing the selected profile and requesting its secondary public API/JSON endpoints…"
                            color: Theme.textSecondary
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Rectangle {
                        visible: root.accountEnrichmentMatchesSelectedAccount() && !root.accountEnrichmentBusy
                        width: parent.width
                        height: enrichmentSummaryColumn.height + 24
                        radius: 8
                        color: Theme.surfaceHover
                        border.width: 1
                        border.color: Theme.divider

                        Column {
                            id: enrichmentSummaryColumn
                            x: 12
                            y: 12
                            width: parent.width - 24
                            spacing: 6

                            Text {
                                width: parent.width
                                text: String(root.accountEnrichment.connector || "Maigret")
                                    + " · " + String(root.accountEnrichment.site || "")
                                    + (root.accountEnrichment.durationText ? " · " + String(root.accountEnrichment.durationText) : "")
                                color: Theme.textPrimary
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                visible: Boolean(root.accountEnrichment.error)
                                width: parent.width
                                text: String(root.accountEnrichment.error || "")
                                color: Theme.warning
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                            Text {
                                visible: !root.accountEnrichment.error && (root.accountEnrichment.fields || []).length === 0
                                width: parent.width
                                text: "The selected account was checked, but no additional structured fields were extracted."
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    Repeater {
                        model: root.accountEnrichmentMatchesSelectedAccount() ? (root.accountEnrichment.fields || []) : []
                        delegate: Rectangle {
                            id: enrichmentFieldRow
                            required property var modelData
                            width: accountDetailsColumn.width
                            height: enrichmentFieldValue.contentHeight + 34
                            radius: 7
                            color: Theme.surfaceHover
                            border.width: 1
                            border.color: Theme.divider

                            Text {
                                x: 12
                                y: 8
                                width: parent.width * 0.30 - 16
                                text: String(enrichmentFieldRow.modelData.label || enrichmentFieldRow.modelData.key || "Field")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            TextEdit {
                                id: enrichmentFieldValue
                                x: parent.width * 0.30
                                y: 8
                                width: parent.width * 0.70 - 12
                                text: String(enrichmentFieldRow.modelData.value || "")
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.WrapAnywhere
                            }
                        }
                    }

                    Text {
                        width: parent.width
                        text: "Provider metadata is shown as reported by the source. It may contain service-specific fields and does not by itself prove that multiple accounts belong to the same person."
                        color: Theme.textMuted
                        font.pixelSize: 9
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }

    Dialog {
        id: newSearchPersonDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, root.width - 80)
        height: 320
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Theme.divider
                }
                Text {
                    x: 20
                    y: 13
                    text: "Create search person"
                    color: Theme.textPrimary
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }
                Text {
                    x: 20
                    y: 41
                    width: parent.width - 40
                    text: "Creates a PERSON in this investigation and selects it as the target for the next search."
                    color: Theme.textMuted
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 20
                spacing: 10

                Text { text: "NAME"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }

                AppTextField {
                    id: newSearchPersonName
                    Layout.fillWidth: true
                    placeholderText: "Full name / investigation label"
                }

                Text { text: "DESCRIPTION"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }

                AppTextField {
                    id: newSearchPersonDescription
                    Layout.fillWidth: true
                    placeholderText: "Optional note"
                }

                Text {
                    id: newSearchPersonError
                    Layout.fillWidth: true
                    color: Theme.danger
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    AppButton {
                        text: "Cancel"
                        Layout.preferredWidth: 96
                        onClicked: newSearchPersonDialog.close()
                    }

                    AppButton {
                        text: "Create & select"
                        primary: true
                        Layout.preferredWidth: 130
                        enabled: newSearchPersonName.text.trim().length > 0
                        onClicked: {
                            newSearchPersonError.text = ""
                            var result = desktopBridge.createPerson(
                                newSearchPersonName.text,
                                newSearchPersonDescription.text
                            )
                            if (result && result.ok) {
                                root.reloadTargetPeople(String(result.id || ""))
                                newSearchPersonDialog.close()
                            } else {
                                newSearchPersonError.text = result && result.error
                                    ? String(result.error)
                                    : "Unable to create person."
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: mentionPersonDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(560, root.width - 80)
        height: 340
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                Text { x: 20; y: 13; text: "Add mention to person"; color: Theme.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text { x: 20; y: 41; width: parent.width - 40; text: "Creates analyst-selected provenance Evidence; it does not mark identity as verified."; color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.topMargin: 14
                Layout.bottomMargin: 16
                spacing: 10

                Text { text: "MENTION"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                Text {
                    Layout.fillWidth: true
                    text: String(root.selectedMention.title || "Corroborating mention")
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: String(root.selectedMention.mentionSummary || "")
                    color: Theme.textSecondary
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }

                Text { text: "PERSON"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                AppComboBox {
                    id: mentionPersonBox
                    Layout.fillWidth: true
                    model: root.mentionPersonOptions
                    textRole: "label"
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.mentionPersonOptions.length === 0
                    text: "No PERSON entities are available in the selected investigation."
                    color: Theme.warning
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.mentionLinkError.length > 0
                    text: root.mentionLinkError
                    color: Theme.danger
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Cancel"; Layout.preferredWidth: 96; onClicked: mentionPersonDialog.close() }
                    AppButton {
                        text: "Add mention"
                        primary: true
                        Layout.preferredWidth: 120
                        enabled: root.mentionPersonOptions.length > 0 && mentionPersonBox.currentIndex >= 0
                        onClicked: {
                            root.mentionLinkError = ""
                            var selected = root.mentionPersonOptions[mentionPersonBox.currentIndex]
                            var result = investigationSearchBridge.addMentionToPerson(
                                selected ? String(selected.id || "") : "",
                                root.selectedMention
                            )
                            if (result && result.ok) {
                                mentionPersonDialog.close()
                            } else {
                                root.mentionLinkError = result && result.error
                                    ? String(result.error)
                                    : "Unable to attach mention."
                            }
                        }
                    }
                }
            }
        }
    }

}
