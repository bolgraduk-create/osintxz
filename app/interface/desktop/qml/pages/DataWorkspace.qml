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
    property bool actionEnabled: false
    property string actionReason: ""
    signal primaryActionRequested()
    signal recordActivated(string recordId)
    signal recordOptionsRequested(string recordId, string recordTitle)
    property string filterText: ""
    property bool loading: false
    property bool hasMore: false
    property bool updatingRecords: false
    property bool recordsInteractive: root.pageKey === "cases"
    property var liveData: ({ metrics: [], records: [], contextItems: [], emptyText: "No records available", actionEnabled: false, actionReason: "" })

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

            Rectangle {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 142
                height: 38
                radius: 7
                opacity: root.actionEnabled ? 1 : 0.42
                color: root.actionEnabled && actionMouse.containsMouse ? "#2f75df" : Theme.accent
                Behavior on color { ColorAnimation { duration: Motion.hover } }
                Text {
                    anchors.centerIn: parent
                    text: "+   " + root.primaryAction
                    color: "white"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    id: actionMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: root.actionEnabled
                    cursorShape: root.actionEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: root.primaryActionRequested()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 112
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
                            color: recordMouse.containsMouse ? "#142735" : "transparent"
                            Behavior on color { ColorAnimation { duration: Motion.hover } }

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
                                width: 36
                                height: 36
                                radius: 8
                                color: recordRow.modelData.tint || "#142b47"
                                Image {
                                    anchors.centerIn: parent
                                    width: 21
                                    height: 21
                                    source: root.iconSource
                                }
                            }
                            Text {
                                x: 65
                                y: 12
                                width: parent.width - 310
                                text: recordRow.modelData.title
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            Text {
                                x: 65
                                y: 34
                                width: parent.width - 310
                                text: recordRow.modelData.detail
                                color: Theme.textMuted
                                elide: Text.ElideRight
                                font.pixelSize: 10
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            Rectangle {
                                anchors.right: metaLabel.left
                                anchors.rightMargin: 22
                                anchors.verticalCenter: parent.verticalCenter
                                width: statusLabel.implicitWidth + 22
                                height: 26
                                radius: 7
                                color: recordRow.modelData.tint || "#142b47"
                                border.color: recordRow.modelData.color || Theme.accent
                                Text {
                                    id: statusLabel
                                    anchors.centerIn: parent
                                    text: recordRow.modelData.status
                                    color: recordRow.modelData.color
                                    font.pixelSize: 10
                                }
                            }
                            Text {
                                id: metaLabel
                                anchors.right: parent.right
                                anchors.rightMargin: root.recordsInteractive ? 48 : 20
                                anchors.verticalCenter: parent.verticalCenter
                                text: recordRow.modelData.meta
                                color: Theme.textMuted
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            MouseArea {
                                id: recordMouse
                                anchors.fill: parent
                                enabled: root.recordsInteractive
                                hoverEnabled: true
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.recordActivated(String(recordRow.modelData.id || ""))
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 17
                                anchors.verticalCenter: parent.verticalCenter
                                visible: root.recordsInteractive
                                text: "•••"
                                color: optionsMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary
                                font.pixelSize: 11
                                MouseArea {
                                    id: optionsMouse
                                    anchors.fill: parent
                                    anchors.margins: -10
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
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
                        height: root.records.length === 0 ? 132 : 0
                        visible: root.records.length === 0
                        Text {
                            anchors.centerIn: parent
                            text: root.emptyText
                            color: Theme.textMuted
                            font.pixelSize: 13
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
