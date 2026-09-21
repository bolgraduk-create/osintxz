pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import "../components"
import "../theme"

Item {
    id: root

    property var person: desktopBridge.currentEntity || ({})
    property var links: person.links || []
    property var photos: person.photos || []
    property var files: person.files || []
    property var attachmentRows: (photos || []).concat(files || [])
    property var evidenceRows: person.evidence || []
    property var relatedRows: person.relatedEntities || []
    property var profileCandidates: person.profileCandidates || []
    property var profileRows: []
    property var metadataRows: person.metadataRows || []
    // R13.23 PERSON CARD V2
    property var contactRows: []
    property var organizationRows: []
    property var locationRows: []
    property var technicalRows: []
    property var otherIntelligenceRows: []
    property var intelligenceGroups: []
    property var summaryMetrics: []
    // R13.27a UNIFIED TARGET PROFILE
    property var unifiedProfile: ({})
    property var unifiedGroups: []
    property var unifiedProvenance: []
    property var profileCoverage: ({})
    // R13.23.1 PERSON CARD POLISH + MENTIONS
    property var webRows: []
    property var mentionRows: []
    property var reviewRows: []
    property string addError: ""
    property string candidateQuery: ""
    property string candidateError: ""


    function buildProfileRows() {
        var rows = []
        var seen = ({})

        function pushRow(label, value, url, detail, basis) {
            var v = String(value || "").trim()
            var u = String(url || "").trim()
            if (!v.length && !u.length) return
            var key = (u.length ? u : v).toLowerCase()
            if (seen[key]) return
            seen[key] = true
            rows.push({
                label: String(label || "Profile / account"),
                value: v.length ? v : u,
                url: u,
                detail: String(detail || ""),
                basis: String(basis || "")
            })
        }

        for (var i = 0; i < root.relatedRows.length; ++i) {
            var item = root.relatedRows[i]
            var rawType = String(item.rawType || item.type || "").toLowerCase().replace(/ /g, "_")
            if (rawType === "username" || rawType === "account") {
                pushRow(
                    rawType === "username" ? "Username" : "Account",
                    item.value,
                    item.url,
                    item.evidenceTitle || item.type || "Linked intelligence",
                    item.basis
                )
            }
        }

        for (var j = 0; j < root.links.length; ++j) {
            var link = root.links[j]
            pushRow(
                link.label || "Profile / page",
                link.value || link.url,
                link.url,
                link.source || "Explicit profile URL",
                link.basis
            )
        }
        return rows
    }

    function normalizeReviewKey(value) {
        var text = String(value || "").trim().toLowerCase()
        while (text.length > 1 && text.endsWith("/")) text = text.slice(0, -1)
        return text
    }

    function rebuildReviewRows() {
        var known = ({})
        function addKnown(value) {
            var key = root.normalizeReviewKey(value)
            if (key.length) known[key] = true
        }

        addKnown(root.person.title)
        addKnown(root.person.normalizedValue)
        for (var i = 0; i < root.relatedRows.length; ++i) {
            addKnown(root.relatedRows[i].value)
            addKnown(root.relatedRows[i].url)
        }
        for (var j = 0; j < root.links.length; ++j) {
            addKnown(root.links[j].value)
            addKnown(root.links[j].url)
        }
        for (var k = 0; k < root.profileRows.length; ++k) {
            addKnown(root.profileRows[k].value)
            addKnown(root.profileRows[k].url)
        }

        var review = []
        for (var n = 0; n < root.profileCandidates.length; ++n) {
            var candidate = root.profileCandidates[n]
            var originKey = root.normalizeReviewKey(candidate.origin)
            var valueKey = root.normalizeReviewKey(candidate.value)
            var urlKey = root.normalizeReviewKey(candidate.url)
            if ((originKey.length && known[originKey])
                    || (valueKey.length && known[valueKey])
                    || (urlKey.length && known[urlKey])) {
                review.push(candidate)
            }
        }
        root.reviewRows = review
    }

    function rebuildIntelligenceSections() {
        var contacts = []
        var organizations = []
        var locations = []
        var web = []
        var technical = []
        var other = []
        var profileKeys = ({})

        for (var p = 0; p < root.profileRows.length; ++p) {
            var profileKey = root.normalizeReviewKey(root.profileRows[p].url || root.profileRows[p].value)
            if (profileKey.length) profileKeys[profileKey] = true
        }

        for (var i = 0; i < root.relatedRows.length; ++i) {
            var item = root.relatedRows[i]
            var rawType = String(item.rawType || item.type || "")
                .toLowerCase().replace(/ /g, "_")

            if (rawType === "username" || rawType === "account")
                continue
            if (rawType === "email" || rawType === "phone")
                contacts.push(item)
            else if (rawType === "organization")
                organizations.push(item)
            else if (rawType === "location" || rawType === "address")
                locations.push(item)
            else if (rawType === "url") {
                var webKey = root.normalizeReviewKey(item.url || item.value)
                if (!webKey.length || !profileKeys[webKey]) web.push(item)
            }
            else if (rawType === "domain" || rawType === "ip" || rawType === "asn" || rawType === "hash")
                technical.push(item)
            else
                other.push(item)
        }

        root.contactRows = contacts
        root.organizationRows = organizations
        root.locationRows = locations
        root.webRows = web
        root.technicalRows = technical
        root.otherIntelligenceRows = other
        root.rebuildReviewRows()

        var groups = [
            { title: "CONTACTS", rows: contacts, empty: "No linked contacts" },
            { title: "ORGANIZATIONS", rows: organizations, empty: "No linked organizations" },
            { title: "LOCATIONS", rows: locations, empty: "No linked locations" },
            { title: "WEB PROFILES / PAGES", rows: web, empty: "No additional linked pages" },
            // R13.23.1.1 EMPTY-STATE COMPATIBILITY
            { title: "TECHNICAL", rows: technical, empty: "No web / network identifiers" }
        ]
        if (other.length > 0)
            groups.push({ title: "OTHER INTELLIGENCE", rows: other, empty: "" })
        root.intelligenceGroups = groups
        var backendMetrics = root.unifiedProfile.metrics || []
        root.summaryMetrics = backendMetrics.length > 0 ? backendMetrics : [
            { label: "Accounts", value: root.profileRows.length },
            { label: "Contacts", value: contacts.length },
            { label: "Organizations", value: organizations.length },
            { label: "Locations", value: locations.length },
            { label: "Mentions", value: root.mentionRows.length },
            { label: "Evidence", value: root.evidenceRows.length },
            { label: "Review", value: root.reviewRows.length }
        ]
    }

    function unifiedProvenanceText() {
        var rows = root.unifiedProvenance || []
        if (!rows.length) return "No linked provenance yet"
        var parts = []
        for (var i = 0; i < rows.length && i < 4; ++i) {
            parts.push(String(rows[i].label || rows[i].basis || "Source") + " " + String(rows[i].count || 0))
        }
        return parts.join(" · ")
    }

    function intelligenceRowDetail(item) {
        var parts = []
        var rawType = String(item.rawType || item.type || "").replace(/_/g, " ")
        if (rawType.length) parts.push(rawType)
        if (item.basis === "analyst_selected") parts.push("analyst linked")
        else if (item.basis === "manual") parts.push("manual")
        else if (item.basis) parts.push(String(item.basis))
        if (item.evidenceTitle) parts.push(String(item.evidenceTitle))
        return parts.join(" · ")
    }

    function attachmentKind() {
        var kinds = ["link", "photo", "file", "email", "phone", "username", "note"]
        return kinds[Math.max(0, addType.currentIndex)]
    }

    function isFileKind() {
        var kind = attachmentKind()
        return kind === "photo" || kind === "file"
    }

    function resetAddForm() {
        addTitle.text = ""
        addValue.text = ""
        addDescription.text = ""
        addError = ""
    }

    function filteredProfileCandidates() {
        var query = String(root.candidateQuery || "").trim().toLowerCase()
        if (!query.length) return root.reviewRows
        var result = []
        for (var i = 0; i < root.reviewRows.length; ++i) {
            var item = root.reviewRows[i]
            var haystack = (String(item.value || "") + " "
                + String(item.typeLabel || item.type || "") + " "
                + String(item.connector || "") + " "
                + String(item.source || "") + " "
                + String(item.origin || "")).toLowerCase()
            if (haystack.indexOf(query) >= 0) result.push(item)
        }
        return result
    }

    function reload() {
        root.person = desktopBridge.currentEntity || ({})
        root.links = root.person.links || []
        root.photos = root.person.photos || []
        root.files = root.person.files || []
        root.evidenceRows = root.person.evidence || []
        root.mentionRows = root.person.mentions || []
        root.relatedRows = root.person.relatedEntities || []
        root.profileCandidates = root.person.profileCandidates || []
        root.metadataRows = root.person.metadataRows || []
        root.unifiedProfile = root.person.unifiedProfile || ({})
        root.unifiedGroups = root.unifiedProfile.groups || []
        root.unifiedProvenance = root.unifiedProfile.provenance || []
        root.profileCoverage = root.unifiedProfile.coverage || ({})
        root.profileRows = root.buildProfileRows()
        root.rebuildIntelligenceSections()
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.reload() }
    }

    opacity: 0
    Component.onCompleted: {
        root.reload()
        appear.start()
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
        anchors.topMargin: 18
        anchors.bottomMargin: 26
        spacing: Spacing.panelGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 90
            Layout.minimumHeight: 90
            Layout.maximumHeight: 90

            AppButton {
                anchors.left: parent.left
                anchors.top: parent.top
                width: 116
                height: 34
                text: "←  Entities"
                onClicked: desktopBridge.closeEntity()
            }

            Text {
                x: 136
                y: 0
                text: "PERSON INTELLIGENCE"
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 136
                y: 20
                width: Math.max(160, parent.width - 320)
                text: String(root.person.title || "Person")
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                x: 137
                y: 62
                width: Math.max(160, parent.width - 300)
                text: (root.person.caseTitle ? String(root.person.caseTitle) + " · " : "")
                    + "Entity confidence " + String(root.person.confidenceText || "—")
                color: Theme.textSecondary
                font.pixelSize: 12
                elide: Text.ElideRight
            }


            AppButton {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 142
                height: 36
                text: "+  Add item"
                enabled: String(root.person.id || "").length > 0
                onClicked: {
                    root.resetAddForm()
                    addDialog.open()
                }
            }

            AppButton {
                anchors.right: parent.right
                anchors.rightMargin: 152
                anchors.top: parent.top
                width: 162
                height: 36
                text: "+  From intelligence"
                enabled: root.reviewRows.length > 0
                onClicked: profileCandidateDialog.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.panelGap

            Panel {
                Layout.preferredWidth: 390
                Layout.maximumWidth: 430
                Layout.fillHeight: true
                title: "Person Overview"
                subtitle: "Stored identity record and provenance"
                iconSource: "../../assets/icons/users_purple.svg"

                Flickable {
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: overviewColumn.height
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: overviewColumn
                        width: parent.width
                        spacing: 0

                        Rectangle {
                            width: parent.width
                            height: 108
                            color: "transparent"

                            CircularAvatar {
                                x: 18
                                y: 18
                                width: 72
                                height: 72
                                source: String(root.person.avatarUrl || "")
                                fallbackSource: "../../assets/icons/users_purple.svg"
                                backgroundColor: "#2a2140"
                                borderColor: "#a98be9"
                                borderWidth: 1
                                inset: source.toString().length > 0 ? 2 : 0
                            }

                            Text {
                                x: 102
                                y: 25
                                width: parent.width - 120
                                text: String(root.person.title || "Unnamed person")
                                color: Theme.textPrimary
                                font.pixelSize: 17
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                x: 102
                                y: 52
                                width: parent.width - 120
                                text: "PERSON ENTITY · " + String(root.person.confidenceText || "—")
                                color: "#a98be9"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                font.letterSpacing: 0.8
                            }
                            Text {
                                x: 102
                                y: 74
                                width: parent.width - 120
                                text: String(root.person.caseTitle || "No case label")
                                color: Theme.textMuted
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Repeater {
                            model: [
                                { label: "NORMALIZED IDENTITY", value: root.person.normalizedValue || "—" },
                                { label: "CREATED", value: root.person.createdAt || "—" },
                                { label: "UPDATED", value: root.person.updatedAt || "—" }
                            ]
                            delegate: Rectangle {
                                id: overviewRow
                                required property var modelData
                                width: overviewColumn.width
                                height: 62
                                color: "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 18; y: 11; text: String(overviewRow.modelData.label); color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                                Text { x: 18; y: 31; width: parent.width - 36; text: String(overviewRow.modelData.value); color: Theme.textPrimary; font.pixelSize: 11; elide: Text.ElideRight }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: descriptionText.implicitHeight + 42
                            color: "transparent"
                            Text { x: 18; y: 11; text: "DESCRIPTION"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                            Text {
                                id: descriptionText
                                x: 18
                                y: 31
                                width: parent.width - 36
                                text: String(root.person.description || "No description")
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                            }
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        }

                        Repeater {
                            model: root.metadataRows
                            delegate: Rectangle {
                                id: metadataRow
                                required property var modelData
                                width: overviewColumn.width
                                height: 58
                                color: "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 18; y: 10; text: String(metadataRow.modelData.label || "METADATA").toUpperCase(); color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 0.9 }
                                Text { x: 18; y: 29; width: parent.width - 36; text: String(metadataRow.modelData.value || "—"); color: Theme.textPrimary; font.pixelSize: 10; elide: Text.ElideRight }
                            }
                        }
                    }

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }

            Flickable {
                id: rightDetailScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: rightDetailColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: rightDetailColumn
                    width: rightDetailScroll.width
                    spacing: Spacing.panelGap

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 166
                    Layout.minimumHeight: 166
                    Layout.maximumHeight: 166
                    title: "Intelligence Summary"
                    subtitle: "Unified Target Profile · "
                        + (root.profileCoverage.label
                            ? String(root.profileCoverage.label) + " · "
                            : "")
                        + root.unifiedProvenanceText()
                        + " · provenance remains authoritative"
                    iconSource: "../../assets/icons/chart_blue.svg"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        Repeater {
                            model: root.summaryMetrics
                            delegate: Rectangle {
                                id: summaryMetric
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 72
                                radius: 8
                                color: "#0d1f2c"
                                border.width: 1
                                border.color: Theme.border
                                Text {
                                    x: 12; y: 11
                                    text: String(summaryMetric.modelData.label || "Metric").toUpperCase()
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    font.letterSpacing: 0.8
                                }
                                Text {
                                    x: 12; y: 34
                                    text: String(summaryMetric.modelData.value || 0)
                                    color: Theme.textPrimary
                                    font.pixelSize: 22
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(560, Math.max(352, 94 + Math.ceil(root.intelligenceGroups.length / 2) * 132))
                    Layout.minimumHeight: 352
                    Layout.maximumHeight: 560
                    title: "Core Intelligence"
                    subtitle: "Evidence-linked profile sections · grouped view does not change association provenance"
                    iconSource: "../../assets/icons/users_cyan.svg"

                    GridLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        columns: 2
                        rowSpacing: 10
                        columnSpacing: 10

                        Repeater {
                            model: root.intelligenceGroups
                            delegate: Rectangle {
                                id: intelligenceGroup
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 126
                                radius: 8
                                color: "#0d1f2c"
                                border.width: 1
                                border.color: Theme.border

                                Text {
                                    x: 12; y: 10
                                    width: parent.width - 60
                                    text: String(intelligenceGroup.modelData.title || "INTELLIGENCE")
                                    color: Theme.textSecondary
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                    elide: Text.ElideRight
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 12
                                    y: 10
                                    text: String((intelligenceGroup.modelData.rows || []).length)
                                    color: Theme.accent
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                }

                                Column {
                                    x: 12
                                    y: 34
                                    width: parent.width - 24
                                    spacing: 5

                                    Repeater {
                                        model: (intelligenceGroup.modelData.rows || []).slice(0, 3)
                                        delegate: Item {
                                            id: groupedRow
                                            required property var modelData
                                            width: parent.width
                                            height: 25
                                            Text {
                                                width: parent.width
                                                text: String(groupedRow.modelData.value || "—")
                                                color: groupedRow.modelData.url ? Theme.accent : Theme.textPrimary
                                                font.pixelSize: 10
                                                font.weight: Font.Medium
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                y: 13
                                                width: parent.width
                                                text: root.intelligenceRowDetail(groupedRow.modelData)
                                                color: Theme.textMuted
                                                font.pixelSize: 7
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }

                                    Text {
                                        visible: (intelligenceGroup.modelData.rows || []).length === 0
                                        text: String(intelligenceGroup.modelData.empty || "No linked intelligence")
                                        color: Theme.textMuted
                                        font.pixelSize: 9
                                    }
                                    Text {
                                        visible: (intelligenceGroup.modelData.rows || []).length > 3
                                        text: "+ " + String((intelligenceGroup.modelData.rows || []).length - 3) + " more"
                                        color: Theme.accent
                                        font.pixelSize: 8
                                    }
                                }
                            }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(420, Math.max(210, 96 + root.profileRows.length * 66))
                    Layout.minimumHeight: 210
                    Layout.maximumHeight: 420
                    title: "Profiles & Accounts"
                    subtitle: root.profileRows.length > 0
                        ? String(root.profileRows.length) + " linked profile/account item(s)"
                        : "Select existing OSINT intelligence or add an account manually"
                    iconSource: "../../assets/icons/globe_blue.svg"

                    Item {
                        anchors.fill: parent

                        EmptyState {
                            anchors.fill: parent
                            anchors.margins: 14
                            visible: root.profileRows.length === 0
                            iconSource: "../../assets/icons/globe_blue.svg"
                            title: "No linked accounts yet"
                            description: "Use From intelligence to associate an existing OSINT username/account with this person."
                        }

                        ListView {
                            anchors.fill: parent
                            visible: root.profileRows.length > 0
                            clip: true
                            model: root.profileRows
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                id: profileRow
                                required property var modelData
                                width: ListView.view.width
                                height: 66
                                color: profileMouse.containsMouse ? Theme.surfaceHover : "transparent"

                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }

                                Rectangle {
                                    x: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 34
                                    height: 34
                                    radius: 17
                                    color: "#132d47"
                                    border.width: 1
                                    border.color: "#315b7d"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "@"
                                        color: Theme.accent
                                        font.pixelSize: 16
                                        font.weight: Font.DemiBold
                                    }
                                }

                                Text {
                                    x: 60; y: 9; width: parent.width - 150
                                    text: String(profileRow.modelData.label || "Profile / account")
                                    color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight
                                }
                                Text {
                                    x: 60; y: 29; width: parent.width - 150
                                    text: String(profileRow.modelData.value || "")
                                    color: profileRow.modelData.url ? Theme.accent : Theme.textSecondary
                                    font.pixelSize: 10; elide: Text.ElideRight
                                }
                                Text {
                                    x: 60; y: 47; width: parent.width - 150
                                    text: String(profileRow.modelData.detail || "Linked intelligence")
                                    color: Theme.textMuted
                                    font.pixelSize: 8; elide: Text.ElideRight
                                }

                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 70
                                    height: 24
                                    radius: 12
                                    color: profileRow.modelData.basis === "analyst_selected" ? "#12382f" : "#142b47"
                                    border.width: 1
                                    border.color: profileRow.modelData.basis === "analyst_selected" ? "#1e745f" : "#28527a"
                                    Text {
                                        anchors.centerIn: parent
                                        text: profileRow.modelData.url ? "OPEN ↗" : "LINKED"
                                        color: profileRow.modelData.url ? Theme.accent : Theme.success
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                }

                                MouseArea {
                                    id: profileMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: profileRow.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    enabled: String(profileRow.modelData.url || "").length > 0
                                    onClicked: desktopBridge.openExternalUrl(String(profileRow.modelData.url || ""))
                                }
                            }
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(420, Math.max(210, 96 + root.mentionRows.length * 78))
                    Layout.minimumHeight: 210
                    Layout.maximumHeight: 420
                    title: "Corroborating Mentions"
                    subtitle: root.mentionRows.length > 0
                        ? String(root.mentionRows.length) + " analyst-linked multi-signal mention(s)"
                        : "Attach a multi-signal mention from Investigation Search"
                    iconSource: "../../assets/icons/search.svg"

                    Item {
                        anchors.fill: parent
                        EmptyState {
                            anchors.fill: parent
                            anchors.margins: 14
                            visible: root.mentionRows.length === 0
                            iconSource: "../../assets/icons/search.svg"
                            title: "No corroborating mentions"
                            description: "In Search → Mentions, use Add to person to preserve a relevant page/document with matched signals and provenance."
                        }
                        ListView {
                            anchors.fill: parent
                            visible: root.mentionRows.length > 0
                            clip: true
                            model: root.mentionRows
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                id: mentionRow
                                required property var modelData
                                width: ListView.view.width
                                height: 78
                                color: mentionMouse.containsMouse ? Theme.surfaceHover : "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 16; y: 10; width: parent.width - 170; text: String(mentionRow.modelData.title || "Corroborating mention"); color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Text { x: 16; y: 31; width: parent.width - 170; text: String(mentionRow.modelData.summary || "Multi-signal match"); color: Theme.textSecondary; font.pixelSize: 9; elide: Text.ElideRight }
                                Text { x: 16; y: 51; width: parent.width - 170; text: String(mentionRow.modelData.source || "Source") + (mentionRow.modelData.date ? " · " + String(mentionRow.modelData.date) : ""); color: Theme.textMuted; font.pixelSize: 8; elide: Text.ElideRight }
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 126
                                    height: 28
                                    radius: 6
                                    color: "transparent"
                                    border.width: 1
                                    border.color: Theme.success
                                    Text { anchors.centerIn: parent; text: "MENTION · " + Number(mentionRow.modelData.score || 0).toFixed(0); color: Theme.success; font.pixelSize: 8; font.weight: Font.DemiBold }
                                }
                                MouseArea {
                                    id: mentionMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: mentionRow.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    enabled: String(mentionRow.modelData.url || "").length > 0
                                    onClicked: desktopBridge.openExternalUrl(String(mentionRow.modelData.url || ""))
                                }
                            }
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(460, Math.max(250, 100 + root.attachmentRows.length * 104))
                    Layout.minimumHeight: 250
                    Layout.maximumHeight: 460
                    title: "Photos & Files"
                    subtitle: root.attachmentRows.length > 0
                        ? String(root.attachmentRows.length) + " managed attachment(s)"
                        : "Add photos or documents to this person card"
                    iconSource: "../../assets/icons/document_blue.svg"

                    Item {
                        anchors.fill: parent

                        EmptyState {
                            anchors.fill: parent
                            anchors.margins: 14
                            visible: root.attachmentRows.length === 0
                            iconSource: "../../assets/icons/document_blue.svg"
                            title: "No photos or files"
                            description: "Use Add item to attach a managed local copy of a photo or document."
                        }

                        ListView {
                            anchors.fill: parent
                            visible: root.attachmentRows.length > 0
                            clip: true
                            model: root.attachmentRows
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                id: attachmentRow
                                required property var modelData
                                width: ListView.view.width
                                height: 96
                                color: attachmentMouse.containsMouse ? Theme.surfaceHover : "transparent"

                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }

                                Rectangle {
                                    x: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 72
                                    height: 72
                                    radius: 9
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.border
                                    clip: true
                                    Image {
                                        anchors.fill: parent
                                        anchors.margins: attachmentRow.modelData.previewUrl ? 0 : 18
                                        source: attachmentRow.modelData.previewUrl
                                            ? String(attachmentRow.modelData.previewUrl)
                                            : "../../assets/icons/document_blue.svg"
                                        fillMode: attachmentRow.modelData.previewUrl
                                            ? Image.PreserveAspectCrop
                                            : Image.PreserveAspectFit
                                        asynchronous: true
                                        cache: false
                                    }
                                }

                                Text {
                                    x: 100; y: 18; width: parent.width - 180
                                    text: String(attachmentRow.modelData.title || "Attachment")
                                    color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.Medium; elide: Text.ElideRight
                                }
                                Text {
                                    x: 100; y: 42; width: parent.width - 180
                                    text: String(attachmentRow.modelData.type || "File")
                                        + (attachmentRow.modelData.mimeType ? " · " + String(attachmentRow.modelData.mimeType) : "")
                                    color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight
                                }
                                Text {
                                    x: 100; y: 61; width: parent.width - 180
                                    text: String(attachmentRow.modelData.date || "Managed copy")
                                    color: Theme.textMuted; font.pixelSize: 8; elide: Text.ElideRight
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 20
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "↗"
                                    color: Theme.accent
                                    font.pixelSize: 18
                                }
                                MouseArea {
                                    id: attachmentMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: desktopBridge.openManagedAttachment(String(attachmentRow.modelData.managedPath || ""))
                                }
                            }
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(520, Math.max(300, 96 + Math.max(root.relatedRows.length * 58, root.evidenceRows.length * 62)))
                    Layout.minimumHeight: 300
                    Layout.maximumHeight: 520
                    spacing: Spacing.panelGap

                    Panel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        title: "Intelligence Attributes"
                        subtitle: "Evidence-linked identifiers · manual and analyst-linked items remain labeled"
                        iconSource: "../../assets/icons/graph_blue.svg"

                        Item {
                            anchors.fill: parent
                            EmptyState {
                                anchors.fill: parent
                                anchors.margins: 14
                                visible: root.relatedRows.length === 0
                                iconSource: "../../assets/icons/graph_blue.svg"
                                title: "No related identifiers"
                                description: "Linked emails, usernames, URLs and other entities will appear here when supported by shared evidence."
                            }
                            ListView {
                                anchors.fill: parent
                                visible: root.relatedRows.length > 0
                                clip: true
                                model: root.relatedRows
                                boundsBehavior: Flickable.StopAtBounds
                                delegate: Rectangle {
                                    id: relatedRow
                                    required property var modelData
                                    width: ListView.view.width
                                    height: 58
                                    color: "transparent"
                                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                    Text { x: 16; y: 10; width: parent.width - 95; text: String(relatedRow.modelData.value || "Identifier"); color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text {
                                        x: 16; y: 31; width: parent.width - 118
                                        text: String(relatedRow.modelData.type || "Entity")
                                            + (relatedRow.modelData.basis === "analyst_selected" ? " · ANALYST SELECTED" : (relatedRow.modelData.basis === "manual" ? " · MANUAL" : ""))
                                            + (relatedRow.modelData.evidenceTitle ? " · " + String(relatedRow.modelData.evidenceTitle) : "")
                                        color: relatedRow.modelData.basis === "analyst_selected" ? Theme.accent : Theme.textMuted
                                        font.pixelSize: 9
                                        elide: Text.ElideRight
                                    }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: String(relatedRow.modelData.confidence || ""); color: Theme.textSecondary; font.pixelSize: 9 }
                                }
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        title: "Supporting Evidence"
                        subtitle: String(root.evidenceRows.length) + " linked evidence item(s)"
                        iconSource: "../../assets/icons/document_blue.svg"

                        Item {
                            anchors.fill: parent
                            EmptyState {
                                anchors.fill: parent
                                anchors.margins: 14
                                visible: root.evidenceRows.length === 0
                                iconSource: "../../assets/icons/document_blue.svg"
                                title: "No linked evidence"
                                description: "Evidence directly linked to this person entity will appear here."
                            }
                            ListView {
                                anchors.fill: parent
                                visible: root.evidenceRows.length > 0
                                clip: true
                                model: root.evidenceRows
                                boundsBehavior: Flickable.StopAtBounds
                                delegate: Rectangle {
                                    id: evidenceRow
                                    required property var modelData
                                    width: ListView.view.width
                                    height: 62
                                    color: "transparent"
                                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                    Text { x: 16; y: 10; width: parent.width - 86; text: String(evidenceRow.modelData.title || "Evidence"); color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { x: 16; y: 31; width: parent.width - 86; text: String(evidenceRow.modelData.type || "Evidence") + (evidenceRow.modelData.detail ? " · " + String(evidenceRow.modelData.detail) : ""); color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: String(evidenceRow.modelData.date || ""); color: Theme.textMuted; font.pixelSize: 8 }
                                }
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    Layout.minimumHeight: 60
                    Layout.maximumHeight: 60
                    radius: 9
                    color: "#3b3015"
                    border.width: 1
                    border.color: Theme.warning
                    Text {
                        anchors.fill: parent
                        anchors.margins: 13
                        text: String(root.person.associationNotice || "Related identifiers require independent identity verification.")
                        color: Theme.warning
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                }

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            }
        }
    }

    Dialog {
        id: addDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(560, root.width - 80)
        height: 500
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 66
                color: "transparent"
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                Text { x: 20; y: 14; text: "Add to person"; color: Theme.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text { x: 20; y: 39; text: "Manual attachment · stored with provenance"; color: Theme.textMuted; font.pixelSize: 10 }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                spacing: 8

                Text { text: "TYPE"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                AppComboBox {
                    id: addType
                    Layout.fillWidth: true
                    model: ["Link / profile", "Photo", "Document / file", "Email", "Phone", "Username / account", "Analyst note"]
                    onCurrentIndexChanged: {
                        addValue.text = ""
                        root.addError = ""
                    }
                }

                Text { text: "TITLE (OPTIONAL)"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                AppTextField {
                    id: addTitle
                    Layout.fillWidth: true
                    placeholderText: "Example: Main Instagram profile"
                }

                Text { text: root.isFileKind() ? "LOCAL FILE" : "VALUE"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    AppTextField {
                        id: addValue
                        Layout.fillWidth: true
                        readOnly: root.isFileKind()
                        placeholderText: {
                            var kind = root.attachmentKind()
                            if (kind === "link") return "https://..."
                            if (kind === "photo" || kind === "file") return "Choose a local file..."
                            if (kind === "email") return "name@example.com"
                            if (kind === "phone") return "+380..."
                            if (kind === "username") return "username"
                            return "Manual note"
                        }
                    }
                    AppButton {
                        visible: root.isFileKind()
                        Layout.preferredWidth: 94
                        text: "Browse..."
                        onClicked: attachmentFileDialog.open()
                    }
                }

                Text { text: "DESCRIPTION (OPTIONAL)"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                AppTextField {
                    id: addDescription
                    Layout.fillWidth: true
                    placeholderText: "Why this item is relevant / where it came from"
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    radius: 8
                    color: "#162536"
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        anchors.fill: parent
                        anchors.margins: 11
                        text: "Manual identifiers are stored as user-supplied assertions. Adding a profile, email, phone or username does not mark identity as independently verified."
                        color: Theme.textSecondary
                        font.pixelSize: 9
                        wrapMode: Text.Wrap
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.addError.length > 0
                    text: root.addError
                    color: Theme.danger
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 16
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    AppButton {
                        text: "Cancel"
                        Layout.preferredWidth: 100
                        onClicked: addDialog.close()
                    }
                    AppButton {
                        text: "Add item"
                        Layout.preferredWidth: 112
                        enabled: addValue.text.trim().length > 0
                        onClicked: {
                            root.addError = ""
                            var result = desktopBridge.addPersonAttachment(
                                root.attachmentKind(),
                                addTitle.text,
                                addValue.text,
                                addDescription.text
                            )
                            if (result && result.ok) {
                                addDialog.close()
                                root.resetAddForm()
                            } else {
                                root.addError = result && result.error
                                    ? String(result.error)
                                    : "Unable to add attachment."
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: profileCandidateDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(720, root.width - 80)
        height: Math.min(650, root.height - 80)
        padding: 0
        closePolicy: Popup.CloseOnEscape

        onOpened: {
            root.candidateQuery = ""
            root.candidateError = ""
        }

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
                Text { x: 20; y: 13; text: "Add existing intelligence"; color: Theme.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text {
                    x: 20; y: 40; width: parent.width - 40
                    text: "Choose already-persisted OSINT data for this person. Selection records relevance, not verified ownership."
                    color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.topMargin: 12
                Layout.bottomMargin: 14
                spacing: 10

                AppTextField {
                    Layout.fillWidth: true
                    placeholderText: "Filter by value, type, connector, source..."
                    onTextChanged: root.candidateQuery = text
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 9
                    color: "#102230"
                    border.width: 1
                    border.color: Theme.border

                    ListView {
                        id: candidateList
                        anchors.fill: parent
                        clip: true
                        model: root.filteredProfileCandidates()
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            id: candidateRow
                            required property var modelData
                            width: ListView.view.width
                            height: 72
                            color: candidateMouse.containsMouse ? Theme.surfaceHover : "transparent"

                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }

                            Rectangle {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: 42
                                height: 42
                                radius: 21
                                color: "#172d42"
                                border.width: 1
                                border.color: Theme.border
                                Image {
                                    anchors.centerIn: parent
                                    width: 20
                                    height: 20
                                    source: {
                                        var type = String(candidateRow.modelData.type || "")
                                        if (type === "email") return "../../assets/icons/mail_blue.svg"
                                        if (type === "phone") return "../../assets/icons/phone_green.svg"
                                        if (type === "organization") return "../../assets/icons/building_cyan.svg"
                                        if (type === "url" || type === "domain" || type === "ip") return "../../assets/icons/globe_blue.svg"
                                        return "../../assets/icons/users_cyan.svg"
                                    }
                                    fillMode: Image.PreserveAspectFit
                                }
                            }

                            Text {
                                x: 66; y: 11; width: parent.width - 220
                                text: String(candidateRow.modelData.value || "Unnamed intelligence item")
                                color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.Medium; elide: Text.ElideRight
                            }
                            Text {
                                x: 66; y: 31; width: parent.width - 220
                                text: String(candidateRow.modelData.typeLabel || candidateRow.modelData.type || "Entity")
                                    + (candidateRow.modelData.connector ? " · " + String(candidateRow.modelData.connector) : "")
                                    + (candidateRow.modelData.source ? " · " + String(candidateRow.modelData.source) : "")
                                color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight
                            }
                            Text {
                                x: 66; y: 49; width: parent.width - 220
                                text: candidateRow.modelData.origin ? "Origin: " + String(candidateRow.modelData.origin) : "Stored OSINT finding"
                                color: "#6f879a"; font.pixelSize: 8; elide: Text.ElideRight
                            }

                            Text {
                                anchors.right: addExistingButton.left
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(candidateRow.modelData.confidence || "")
                                color: Theme.textSecondary
                                font.pixelSize: 9
                            }

                            AppButton {
                                id: addExistingButton
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: 82
                                height: 30
                                text: "Add"
                                onClicked: {
                                    root.candidateError = ""
                                    var result = desktopBridge.addExistingDataToPerson(String(candidateRow.modelData.id || ""))
                                    if (!(result && result.ok)) {
                                        root.candidateError = result && result.error
                                            ? String(result.error)
                                            : "Unable to add selected intelligence."
                                    }
                                }
                            }

                            MouseArea {
                                id: candidateMouse
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.right: addExistingButton.left
                                hoverEnabled: true
                                acceptedButtons: Qt.NoButton
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: candidateList.count === 0
                        text: root.reviewRows.length === 0
                            ? "No unlinked OSINT profile candidates are currently stored in this investigation."
                            : "No candidates match this filter."
                        color: Theme.textMuted
                        font.pixelSize: 10
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.candidateError.length > 0
                    text: root.candidateError
                    color: Theme.danger
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: String(root.reviewRows.length) + " relevant candidate(s) available"
                        color: Theme.textMuted
                        font.pixelSize: 9
                    }
                    AppButton { Layout.preferredWidth: 90; text: "Close"; onClicked: profileCandidateDialog.close() }
                }
            }
        }
    }

    Dialogs.FileDialog {
        id: attachmentFileDialog
        title: root.attachmentKind() === "photo" ? "Select photo" : "Select file"
        nameFilters: root.attachmentKind() === "photo"
            ? ["Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)", "All files (*)"]
            : ["All files (*)"]
        onAccepted: addValue.text = selectedFile.toString()
    }

}
