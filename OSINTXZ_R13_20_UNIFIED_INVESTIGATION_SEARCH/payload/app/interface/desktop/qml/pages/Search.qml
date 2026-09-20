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
    property var runData: investigationSearchBridge.runData || ({})
    property var summary: runData.summary || ({})
    property var storedResults: []
    property bool busy: investigationSearchBridge.busy

    function itemCount(tab) {
        if (tab === "results") return (runData.results || []).length
        if (tab === "providers") return (runData.providers || []).length
        if (tab === "pivots") return (runData.pivots || []).length
        if (tab === "errors") return (runData.errors || []).length
        return 0
    }

    function tabItems() {
        if (activeTab === "results") return runData.results || []
        if (activeTab === "providers") return runData.providers || []
        if (activeTab === "pivots") return runData.pivots || []
        if (activeTab === "errors") return runData.errors || []
        return []
    }

    function statusColor(status) {
        const value = String(status || "").toLowerCase()
        if (value === "success" || value === "completed" || value === "finding" || value === "registry" || value === "remote") return Theme.success
        if (value === "partial" || value === "guarded" || value === "candidate") return Theme.warning
        if (value === "failed") return Theme.danger
        if (value === "not_configured" || value === "not_supported") return Theme.textMuted
        return Theme.accent
    }

    function rowTitle(row) {
        if (activeTab === "providers") return String(row.source || "Provider")
        if (activeTab === "pivots") return String(row.value || "Pivot")
        if (activeTab === "errors") return String(row.source || row.lane || "Error")
        return String(row.title || "Result")
    }

    function rowDetail(row) {
        if (activeTab === "providers") return String(row.lane || "") + " · " + String(row.detail || "")
        if (activeTab === "pivots") return String(row.kind || "pivot").replace(/_/g, " ").toUpperCase() + " · " + String(row.origin || "discovered")
        if (activeTab === "errors") return String(row.error || "Unknown error")
        return String(row.detail || "")
    }

    function rowBadge(row) {
        if (activeTab === "providers") return String(row.status || "provider").replace(/_/g, " ").toUpperCase()
        if (activeTab === "pivots") return Boolean(row.queued) ? "QUEUED" : "REVIEW"
        if (activeTab === "errors") return "ERROR"
        if (Boolean(row.sensitive)) return "SENSITIVE"
        if (Boolean(row.candidateOnly)) return "CANDIDATE"
        return String(row.status || row.type || "RESULT").replace(/_/g, " ").toUpperCase()
    }

    function rowMeta(row) {
        if (activeTab === "providers") return String(row.records || 0) + " record(s) · D" + Number(row.depth || 0)
        if (activeTab === "pivots") return (row.country ? String(row.country) + " · " : "") + "D" + Number(row.depth || 0)
        if (activeTab === "errors") return String(row.lane || "")
        return String(row.source || "") + (row.meta ? " · " + String(row.meta) : "")
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
                enabled: root.workspaceMode === "investigation" && desktopBridge.hasCurrentCase && !root.busy
                ToolTip.visible: hovered && !enabled
                ToolTip.delay: 400
                ToolTip.text: root.busy ? "A search is already running." : "Select an investigation first."
                onClicked: {
                    root.activeTab = "results"
                    investigationSearchBridge.search(root.profilePayload(), desktopBridge.currentCaseId, root.optionPayload())
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
            Layout.preferredHeight: visible ? 86 : 0
            spacing: Spacing.panelGap

            StatCard {
                Layout.fillWidth: true
                title: "Known Seeds"
                value: String(root.summary.seeds || 0)
                delta: ""
                subtext: root.runData.hasRun ? "Typed values in current search" : "Built from the form at run time"
                iconSource: "../../assets/icons/search.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Results"
                value: String(root.summary.results || 0)
                delta: ""
                subtext: String(root.summary.evidenceCreated || 0) + " evidence saved"
                iconSource: "../../assets/icons/document_blue.svg"
                accentColor: Theme.success
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "Provider Runs"
                value: String(root.summary.providers || 0)
                delta: ""
                subtext: String(root.summary.guarded || 0) + " guarded / explicit-only"
                iconSource: "../../assets/icons/database.svg"
                accentColor: Theme.accent
                chartType: "none"
            }
            StatCard {
                Layout.fillWidth: true
                title: "New Pivots"
                value: String(root.summary.pivots || 0)
                delta: ""
                subtext: pivotCheck.checked ? "Exact identifiers may be followed" : "Automatic pivoting disabled"
                iconSource: "../../assets/icons/graph_blue.svg"
                accentColor: Theme.warning
                chartType: "none"
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
                    ? ("Target context → " + desktopBridge.currentCaseTitle)
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

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }
                        Text { text: "SEARCH POLICY"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
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
                                    ? (String(root.summary.results || 0) + " result(s) · " + String(root.summary.pivots || 0) + " new pivot(s) · " + String(root.summary.errors || 0) + " error(s)")
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
                        height: 44

                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 5
                            Repeater {
                                model: [
                                    { key: "results", label: "Results" },
                                    { key: "providers", label: "Providers" },
                                    { key: "pivots", label: "Pivots" },
                                    { key: "errors", label: "Errors" }
                                ]
                                delegate: Rectangle {
                                    id: tabButton
                                    required property var modelData
                                    property bool selected: root.activeTab === String(modelData.key)
                                    width: tabText.implicitWidth + 22
                                    height: 28
                                    radius: 6
                                    color: selected ? Theme.accentSoft : (tabMouse.containsMouse ? Theme.surfaceHover : "transparent")
                                    Text {
                                        id: tabText
                                        anchors.centerIn: parent
                                        text: String(tabButton.modelData.label) + "  " + root.itemCount(String(tabButton.modelData.key))
                                        color: tabButton.selected ? Theme.textPrimary : Theme.textSecondary
                                        font.pixelSize: 10
                                        font.weight: tabButton.selected ? Font.DemiBold : Font.Normal
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
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
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
                            width: resultList.width
                            height: 78
                            color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"

                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                            Rectangle {
                                x: 16; anchors.verticalCenter: parent.verticalCenter
                                width: 4; height: 46; radius: 2
                                color: root.activeTab === "errors" ? Theme.danger : root.statusColor(row.modelData.status || (row.modelData.queued ? "success" : "candidate"))
                            }
                            Text {
                                x: 30; y: 12; width: parent.width - 240
                                text: root.rowTitle(row.modelData)
                                color: Theme.textPrimary
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 30; y: 35; width: parent.width - 240
                                text: root.rowDetail(row.modelData)
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 30; y: 56; width: parent.width - 240
                                text: root.rowMeta(row.modelData)
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: parent.top
                                anchors.topMargin: 15
                                width: Math.min(175, Math.max(72, badge.implicitWidth + 18))
                                height: 24
                                radius: 6
                                color: "transparent"
                                border.width: 1
                                border.color: root.statusColor(row.modelData.status || (row.modelData.queued ? "success" : "candidate"))
                                Text {
                                    id: badge
                                    anchors.centerIn: parent
                                    text: root.rowBadge(row.modelData)
                                    color: parent.border.color
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.5
                                }
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 14
                                width: 190
                                horizontalAlignment: Text.AlignRight
                                text: String(row.modelData.lane || "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                            }
                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: row.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (row.modelData.url) desktopBridge.openExternalUrl(String(row.modelData.url))
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
                            ? "Switch result tabs or adjust the known data and source policy."
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
                                ? ("Case: " + desktopBridge.currentCaseTitle + " · Classic/Open-Web safe findings persist into the case; Federation and Registry results remain review-first. Raw secret values are never stored.")
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
}
