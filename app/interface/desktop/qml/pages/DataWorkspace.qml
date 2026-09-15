pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root
    property string pageKey: ""
    property string eyebrow: "INTELLIGENCE WORKSPACE"
    property string title: "Workspace"
    property string subtitle: ""
    property url iconSource: "../../assets/icons/folder_blue.svg"
    property string primaryAction: "New item"
    property string searchPlaceholder: "Filter records..."
    property string sectionTitle: "Records"
    property string contextTitle: "Workspace Summary"
    property var metrics: []
    property var records: []
    property var contextItems: []
    property string emptyText: "No records available"
    property string emptyTitle: "No records available"
    property string emptyDescription: "Records will appear here when they are available."
    property string filteredEmptyTitle: "No matching records"
    property string filteredEmptyDescription: "Try a different search term or clear the current filter."
    property var categoryItems: []
    property string selectedCategory: "all"
    property bool actionEnabled: false
    property string actionReason: ""
    signal primaryActionRequested()
    signal categoryRequested(string categoryKey)
    signal recordActivated(string recordId)
    signal recordOptionsRequested(string recordId, string recordTitle)
    property string filterText: ""
    property bool loading: false
    property bool hasMore: false
    property bool updatingRecords: false
    property bool recordsInteractive: root.pageKey === "cases" || root.pageKey === "entities" || root.pageKey === "reports"
    property bool recordOptionsVisible: root.pageKey === "cases"
    property var liveData: ({ metrics: [], records: [], contextItems: [], emptyText: "No records available", actionEnabled: false, actionReason: "" })

    function conciseRecordDetail(record) {
        var detail = String(record.detail || "").replace(/\s+/g, " ").trim()
        if (root.pageKey !== "evidence")
            return detail
        var looksLikePath = /^[A-Za-z]:[\\/]/.test(detail) || /^[/\\]{1,2}[^/\\]/.test(detail)
        var looksLikeRawMetadata = /(^|[;,\s])(sha256|storage_path|evidence_key|connector_metadata|raw_metadata)\s*[:=]/i.test(detail)
        if (!detail || detail === String(record.title || "") || looksLikePath || looksLikeRawMetadata)
            return String(record.status || "Evidence") + " evidence"
        return detail
    }

    function resolvedEmptyTitle() {
        if (root.emptyText.indexOf("Unable") === 0)
            return "Unable to load records"
        if (root.filterText.trim().length > 0)
            return root.filteredEmptyTitle
        return root.emptyTitle
    }

    function resolvedEmptyDescription() {
        if (root.emptyText.indexOf("Unable") === 0)
            return root.emptyText
        if (root.filterText.trim().length > 0)
            return root.filteredEmptyDescription
        return root.emptyDescription
    }

    function reloadData() {
        if (!root.pageKey)
            return
        const previousY = recordsView.contentY
        const previousRecords = root.records
        root.updatingRecords = true
        root.liveData = desktopBridge.pageData(root.pageKey, root.filterText)
        root.metrics = root.liveData.metrics || []
        root.records = root.liveData.records || []
        root.contextItems = root.liveData.contextItems || []
        root.emptyText = root.liveData.emptyText || "No records available"
        root.actionEnabled = Boolean(root.liveData.actionEnabled)
        root.actionReason = root.liveData.actionReason || ""
        root.loading = Boolean(root.liveData.loading)
        root.hasMore = Boolean(root.liveData.hasMore)
        if (previousRecords.length > 0 && root.records.length >= previousRecords.length
                && root.records[0].id === previousRecords[0].id)
            recordsView.contentY = previousY
        root.updatingRecords = false
    }

    Timer { id: filterTimer; interval: 250; repeat: false; onTriggered: root.reloadData() }
    onFilterTextChanged: {
        if (root.pageKey === "search" && root.filterText.length === 0)
            desktopBridge.search("")
        filterTimer.restart()
    }

    Connections {
        target: desktopBridge
        function onChanged() { if (root.visible) root.reloadData() }
    }

    opacity: 0
    Component.onCompleted: {
        reloadData()
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
            Layout.preferredHeight: 75

            Text {
                x: 1
                y: 0
                text: root.eyebrow
                color: Theme.textMuted
                font.pixelSize: 10
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 1
                y: 20
                text: root.title
                color: Theme.textPrimary
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Text {
                x: 2
                y: 57
                text: root.subtitle
                color: Theme.textSecondary
                font.pixelSize: 13
            }

            AppButton {
                objectName: "primaryActionButton"
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 142
                height: 38
                text: "+   " + root.primaryAction
                primary: true
                enabled: root.actionEnabled
                ToolTip.visible: hovered && !enabled && root.actionReason.length > 0
                ToolTip.delay: 450
                ToolTip.text: root.actionReason
                onClicked: root.primaryActionRequested()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: root.categoryItems.length > 0 ? 44 : 0
            Layout.minimumHeight: Layout.preferredHeight
            Layout.maximumHeight: Layout.preferredHeight
            visible: root.categoryItems.length > 0
            clip: true

            Flickable {
                anchors.fill: parent
                contentWidth: categoryRow.width
                contentHeight: height
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.HorizontalFlick
                clip: true

                Row {
                    id: categoryRow
                    height: parent.height
                    spacing: 8

                    Repeater {
                        model: root.categoryItems
                        delegate: Rectangle {
                            id: categoryChip
                            required property var modelData
                            property bool selected: String(categoryChip.modelData.key) === root.selectedCategory
                            width: Math.max(82, chipText.implicitWidth + 28)
                            height: 34
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 8
                            color: selected ? Theme.accentSoft : (chipMouse.containsMouse ? Theme.surfaceHover : Theme.surface)
                            border.width: 1
                            border.color: selected ? Theme.accent : Theme.border

                            Text {
                                id: chipText
                                anchors.centerIn: parent
                                text: String(categoryChip.modelData.label || categoryChip.modelData.key)
                                    + (categoryChip.modelData.count === undefined ? "" : "  " + String(categoryChip.modelData.count))
                                color: categoryChip.selected ? Theme.accent : Theme.textSecondary
                                font.pixelSize: 10
                                font.weight: categoryChip.selected ? Font.DemiBold : Font.Medium
                            }

                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.categoryRequested(String(categoryChip.modelData.key || "all"))
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 112
            Layout.minimumHeight: 112
            Layout.maximumHeight: 112
            spacing: Spacing.panelGap

            Repeater {
                model: root.metrics
                delegate: StatCard {
                    id: metricCard
                    required property var modelData
                    Layout.fillWidth: true
                    title: metricCard.modelData.title
                    value: metricCard.modelData.value
                    delta: metricCard.modelData.delta
                    subtext: metricCard.modelData.subtext
                    iconSource: root.iconSource
                    accentColor: metricCard.modelData.color
                    chartType: metricCard.modelData.chart || "bars"
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
                title: root.sectionTitle
                iconSource: root.iconSource
                actionText: ""

                Item {
                    anchors.fill: parent

                    Item {
                        width: parent.width
                        height: 62
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            height: 38
                            radius: 7
                            color: "#0d1c28"
                            border.color: Theme.border
                            Image {
                                anchors.left: parent.left
                                anchors.leftMargin: 13
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18
                                height: 18
                                source: "../../assets/icons/search.svg"
                            }
                            TextInput {
                                id: filterInput
                                anchors.left: parent.left
                                anchors.leftMargin: 43
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                color: Theme.textPrimary
                                font.pixelSize: 12
                                selectionColor: Theme.accent
                                onTextChanged: root.filterText = text
                                Keys.onReturnPressed: {
                                    if (root.pageKey === "search")
                                        desktopBridge.search(text)
                                }
                            }
                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 43
                                anchors.verticalCenter: parent.verticalCenter
                                visible: filterInput.text.length === 0
                                text: root.searchPlaceholder
                                color: Theme.textMuted
                                font.pixelSize: 12
                            }
                        }
                    }

                    ListView {
                        id: recordsView
                        objectName: "recordsView"
                        y: 62
                        width: parent.width
                        height: parent.height - 62
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        cacheBuffer: 320
                        reuseItems: true
                        model: root.records
                        delegate: Rectangle {
                            id: recordRow
                            required property var modelData
                            width: recordsView.width
                            height: 64
                            clip: true
                            activeFocusOnTab: root.recordsInteractive
                            color: recordMouse.pressed ? "#182e3e" : (recordMouse.containsMouse ? "#142735" : "transparent")
                            border.width: activeFocus ? 1 : 0
                            border.color: activeFocus ? Theme.borderHover : "transparent"
                            Behavior on color { ColorAnimation { duration: Motion.hover } }
                            Keys.onReturnPressed: root.recordActivated(String(recordRow.modelData.id || ""))
                            Keys.onSpacePressed: root.recordActivated(String(recordRow.modelData.id || ""))

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }
                            CircularAvatar {
                                id: personAvatar
                                x: 17
                                anchors.verticalCenter: parent.verticalCenter
                                width: 36
                                height: 36
                                visible: root.pageKey === "entities"
                                    && String(recordRow.modelData.entityType || "").toLowerCase() === "person"
                                source: String(recordRow.modelData.avatarUrl || "")
                                fallbackSource: "../../assets/icons/users_purple.svg"
                                backgroundColor: recordRow.modelData.tint || "#2a2140"
                                borderColor: recordRow.modelData.color || "#a98be9"
                                borderWidth: 1
                                inset: source.toString().length > 0 ? 1 : 0
                            }
                            Rectangle {
                                x: 17
                                anchors.verticalCenter: parent.verticalCenter
                                width: 36
                                height: 36
                                radius: 8
                                color: recordRow.modelData.tint || "#142b47"
                                visible: !personAvatar.visible
                                Image {
                                    anchors.centerIn: parent
                                    width: 21
                                    height: 21
                                    source: root.iconSource
                                }
                            }
                            Text {
                                objectName: "recordTitle"
                                x: 65
                                y: 12
                                width: Math.max(80, parent.width - 302)
                                text: String(recordRow.modelData.title || "Untitled record")
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            Text {
                                objectName: "recordDetail"
                                x: 65
                                y: 34
                                width: Math.max(80, parent.width - 302)
                                text: root.conciseRecordDetail(recordRow.modelData)
                                color: Theme.textMuted
                                elide: Text.ElideRight
                                font.pixelSize: 10
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            Rectangle {
                                anchors.right: parent.right
                                anchors.rightMargin: root.recordsInteractive ? 48 : 18
                                y: 9
                                width: Math.min(174, Math.max(72, statusLabel.implicitWidth + 22))
                                height: 24
                                radius: 6
                                color: recordRow.modelData.tint || "#142b47"
                                border.color: recordRow.modelData.color || Theme.accent
                                Text {
                                    id: statusLabel
                                    objectName: "recordTypeBadgeText"
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    text: String(recordRow.modelData.status || "Record")
                                    color: recordRow.modelData.color || Theme.accent
                                    font.pixelSize: 10
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                }
                            }
                            Text {
                                id: metaLabel
                                objectName: "recordMeta"
                                anchors.right: parent.right
                                anchors.rightMargin: root.recordsInteractive ? 48 : 18
                                y: 39
                                width: 174
                                text: root.pageKey === "evidence" && String(recordRow.modelData.meta || "") === "SHA-256"
                                    ? "HASHED · SHA-256"
                                    : String(recordRow.modelData.meta || "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                elide: Text.ElideRight
                                horizontalAlignment: Text.AlignRight
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            MouseArea {
                                id: recordMouse
                                anchors.fill: parent
                                enabled: root.recordsInteractive && Boolean(recordRow.modelData.interactive !== false)
                                hoverEnabled: true
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onPressed: recordRow.forceActiveFocus()
                                onClicked: root.recordActivated(String(recordRow.modelData.id || ""))
                            }
                            Text {
                                id: entityActionHint
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.verticalCenter: parent.verticalCenter
                                visible: root.pageKey === "entities" && Boolean(recordRow.modelData.interactive !== false)
                                text: String(recordRow.modelData.url || "").length > 0 ? "↗" : "›"
                                color: recordMouse.containsMouse ? Theme.accent : Theme.textSecondary
                                font.pixelSize: 18
                                font.weight: Font.Medium
                            }

                            Text {
                                id: optionsLabel
                                anchors.right: parent.right
                                anchors.rightMargin: 17
                                anchors.verticalCenter: parent.verticalCenter
                                visible: root.recordOptionsVisible
                                activeFocusOnTab: visible
                                text: "•••"
                                color: activeFocus || optionsMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary
                                font.pixelSize: 11
                                Keys.onReturnPressed: root.recordOptionsRequested(String(recordRow.modelData.id || ""), String(recordRow.modelData.title || ""))
                                Keys.onSpacePressed: root.recordOptionsRequested(String(recordRow.modelData.id || ""), String(recordRow.modelData.title || ""))
                                MouseArea {
                                    id: optionsMouse
                                    anchors.fill: parent
                                    anchors.margins: -10
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onPressed: optionsLabel.forceActiveFocus()
                                    onClicked: function(mouse) {
                                        mouse.accepted = true
                                        root.recordOptionsRequested(
                                            String(recordRow.modelData.id || ""),
                                            String(recordRow.modelData.title || "")
                                        )
                                    }
                                }
                            }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        onContentYChanged: {
                            if (!root.updatingRecords && root.hasMore && !root.loading && contentY + height >= contentHeight - 180)
                                desktopBridge.loadMore(root.pageKey)
                        }
                    }

                    Item {
                        y: 62
                        width: parent.width
                        height: root.records.length === 0 ? parent.height - y : 0
                        visible: root.records.length === 0
                        EmptyState {
                            anchors.fill: parent
                            anchors.bottomMargin: 18
                            iconSource: root.iconSource
                            title: root.resolvedEmptyTitle()
                            description: root.resolvedEmptyDescription()
                        }
                    }
                }
            }

            Panel {
                Layout.fillHeight: true
                Layout.preferredWidth: 400
                Layout.maximumWidth: 440
                title: root.contextTitle
                iconSource: "../../assets/icons/chart.svg"

                Column {
                    anchors.fill: parent
                    Repeater {
                        model: root.contextItems
                        delegate: Rectangle {
                            id: contextRow
                            required property var modelData
                            width: parent.width
                            height: 62
                            color: "transparent"
                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }
                            Rectangle {
                                x: 17
                                anchors.verticalCenter: parent.verticalCenter
                                width: 8
                                height: 8
                                radius: 4
                                color: contextRow.modelData.color
                            }
                            Text {
                                x: 39
                                y: 13
                                width: parent.width - 58
                                text: contextRow.modelData.title
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                font.pixelSize: 12
                                font.weight: Font.Medium
                            }
                            Text {
                                x: 39
                                y: 35
                                width: parent.width - 58
                                text: contextRow.modelData.detail
                                color: Theme.textMuted
                                elide: Text.ElideRight
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }
        }
    }
}
