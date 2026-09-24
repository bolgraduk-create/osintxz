pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var payload: desktopBridge.analysisMediaWorkspace || ({})
    property var items: payload.items || []
    property var counts: payload.counts || ({})
    property string mediaFilter: "all"
    property string selectedMediaId: ""
    property var selectedItem: root.findSelectedItem()

    function filteredMediaItems() {
        if (root.mediaFilter === "all")
            return root.items

        var result = []
        for (var i = 0; i < root.items.length; ++i) {
            if (String(root.items[i].type || "") === root.mediaFilter)
                result.push(root.items[i])
        }
        return result
    }

    function filterCount(key) {
        return Number(root.counts[key] || 0)
    }

    function findSelectedItem() {
        for (var i = 0; i < root.items.length; ++i) {
            if (String(root.items[i].id || "") === root.selectedMediaId)
                return root.items[i]
        }
        return ({})
    }

    function ensureSelection() {
        var rows = root.filteredMediaItems()
        if (rows.length === 0) {
            root.selectedMediaId = ""
            return
        }

        for (var i = 0; i < rows.length; ++i) {
            if (String(rows[i].id || "") === root.selectedMediaId)
                return
        }

        root.selectedMediaId = String(rows[0].id || "")
    }

    function typeLabel(value) {
        var key = String(value || "").toLowerCase()
        if (key === "image") return "IMAGE"
        if (key === "video") return "VIDEO"
        if (key === "audio") return "AUDIO"
        return key.toUpperCase()
    }

    function typeIcon(value) {
        var key = String(value || "").toLowerCase()
        if (key === "image") return "../../assets/icons/image.svg"
        if (key === "video") return "../../assets/icons/video.svg"
        if (key === "audio") return "../../assets/icons/clock.svg"
        return "../../assets/icons/document_blue.svg"
    }

    function gpsText(item) {
        var gps = (item || {}).gps || ({})
        if (!gps.available)
            return "No GPS"
        return Number(gps.latitude).toFixed(6)
            + ", "
            + Number(gps.longitude).toFixed(6)
    }

    Component.onCompleted: root.ensureSelection()

    Connections {
        target: desktopBridge
        function onChanged() {
            Qt.callLater(root.ensureSelection)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 16
        anchors.bottomMargin: 22
        spacing: 10

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 68

            Text {
                x: 1
                y: 0
                text: "MULTIMODAL INTELLIGENCE"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.6
            }

            Text {
                x: 1
                y: 18
                text: "Media"
                color: Theme.textPrimary
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }

            Text {
                x: 2
                y: 52
                width: parent.width - 360
                text: root.payload.hasCase
                    ? ("Investigation: " + String(root.payload.caseTitle || "Current investigation"))
                    : "Select an investigation to inspect stored images, video and audio."
                color: Theme.textSecondary
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            Row {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                spacing: 8

                Rectangle {
                    width: analyzedText.implicitWidth + 20
                    height: 28
                    radius: 7
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: analyzedText
                        anchors.centerIn: parent
                        text: String(root.counts.analyzed || 0) + " analyzed"
                        color: Theme.textSecondary
                        font.pixelSize: 9
                    }
                }

                Rectangle {
                    width: gpsTextBadge.implicitWidth + 20
                    height: 28
                    radius: 7
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: gpsTextBadge
                        anchors.centerIn: parent
                        text: String(root.counts.gps || 0) + " GPS"
                        color: Theme.textSecondary
                        font.pixelSize: 9
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            spacing: 6

            Repeater {
                model: [
                    { key: "all", label: "All", countKey: "all" },
                    { key: "image", label: "Images", countKey: "image" },
                    { key: "video", label: "Video", countKey: "video" },
                    { key: "audio", label: "Audio", countKey: "audio" }
                ]

                delegate: Rectangle {
                    id: filterButton
                    required property var modelData
                    property bool selected: root.mediaFilter === String(modelData.key)
                    Layout.preferredWidth: Math.max(92, filterLabel.implicitWidth + 28)
                    Layout.preferredHeight: 30
                    radius: 7
                    color: selected
                        ? Theme.accentSoft
                        : (filterMouse.containsMouse ? Theme.surfaceHover : "transparent")
                    border.width: 1
                    border.color: selected ? Theme.accent : Theme.border

                    Text {
                        id: filterLabel
                        anchors.centerIn: parent
                        text: String(filterButton.modelData.label)
                            + "  "
                            + root.filterCount(String(filterButton.modelData.countKey))
                        color: filterButton.selected ? Theme.textPrimary : Theme.textSecondary
                        font.pixelSize: 10
                        font.weight: filterButton.selected ? Font.DemiBold : Font.Normal
                    }

                    MouseArea {
                        id: filterMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.mediaFilter = String(filterButton.modelData.key)
                            root.ensureSelection()
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "LOCAL STORED MEDIA"
                color: Theme.textMuted
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.panelGap

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Media Library"
                subtitle: String(root.filteredMediaItems().length)
                    + " item(s) in this view · bounded to "
                    + String(root.payload.limit || 300)
                    + " evidence records"
                iconSource: "../../assets/icons/document_blue.svg"

                Item {
                    anchors.fill: parent

                    GridView {
                        id: mediaGrid
                        anchors.fill: parent
                        anchors.margins: 12
                        clip: true
                        cellWidth: 210
                        cellHeight: 178
                        model: root.filteredMediaItems()
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            id: mediaCard
                            required property var modelData
                            width: 198
                            height: 166
                            radius: 9
                            property bool selected: root.selectedMediaId === String(modelData.id || "")
                            color: selected
                                ? Theme.accentSoft
                                : (mediaMouse.containsMouse ? Theme.surfaceHover : Theme.surface)
                            border.width: 1
                            border.color: selected ? Theme.accent : Theme.border
                            clip: true

                            Rectangle {
                                x: 8
                                y: 8
                                width: parent.width - 16
                                height: 98
                                radius: 7
                                color: "#0b1a25"
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    source: String(mediaCard.modelData.previewUrl || "")
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: false
                                    visible: String(mediaCard.modelData.previewUrl || "").length > 0
                                }

                                Image {
                                    anchors.centerIn: parent
                                    width: 34
                                    height: 34
                                    source: root.typeIcon(mediaCard.modelData.type)
                                    fillMode: Image.PreserveAspectFit
                                    opacity: 0.82
                                    visible: String(mediaCard.modelData.previewUrl || "").length === 0
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 7
                                    anchors.top: parent.top
                                    anchors.topMargin: 7
                                    width: typeBadge.implicitWidth + 14
                                    height: 21
                                    radius: 5
                                    color: "#c40b1a25"

                                    Text {
                                        id: typeBadge
                                        anchors.centerIn: parent
                                        text: root.typeLabel(mediaCard.modelData.type)
                                        color: Theme.textPrimary
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                }

                                Rectangle {
                                    visible: Boolean((mediaCard.modelData.gps || {}).available)
                                    anchors.right: parent.right
                                    anchors.rightMargin: 7
                                    anchors.top: parent.top
                                    anchors.topMargin: 7
                                    width: 26
                                    height: 21
                                    radius: 5
                                    color: "#c40b1a25"

                                    Image {
                                        anchors.centerIn: parent
                                        width: 13
                                        height: 13
                                        source: "../../assets/icons/pin_purple.svg"
                                    }
                                }
                            }

                            Text {
                                x: 10
                                y: 114
                                width: parent.width - 20
                                text: String(mediaCard.modelData.title || "Untitled media")
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 10
                                y: 136
                                width: parent.width - 20
                                text: String(mediaCard.modelData.dateTaken || mediaCard.modelData.date || mediaCard.modelData.mimeType || "")
                                color: Theme.textMuted
                                font.pixelSize: 8
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                id: mediaMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedMediaId = String(mediaCard.modelData.id || "")
                                onDoubleClicked: desktopBridge.focusWorkspaceRecord(
                                    "evidence",
                                    String(mediaCard.modelData.id || "")
                                )
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }

                    EmptyState {
                        anchors.fill: parent
                        anchors.margins: 18
                        visible: mediaGrid.count === 0
                        iconSource: "../../assets/icons/document_blue.svg"
                        title: root.payload.hasCase ? "No media in this view" : "No investigation selected"
                        description: root.payload.hasCase
                            ? "Imported IMAGE, VIDEO and AUDIO evidence will appear here automatically."
                            : "Select an investigation before opening the Media workspace."
                    }
                }
            }

            Panel {
                Layout.preferredWidth: 380
                Layout.maximumWidth: 420
                Layout.fillHeight: true
                title: "Inspector"
                subtitle: String(root.selectedItem.id || "").length > 0
                    ? root.typeLabel(root.selectedItem.type)
                    : "Select a media item"
                iconSource: "../../assets/icons/search.svg"

                Flickable {
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: inspectorColumn.height + 20
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: inspectorColumn
                        x: 14
                        width: parent.width - 28
                        spacing: 10

                        Item { width: 1; height: 2 }

                        Rectangle {
                            width: parent.width
                            height: 178
                            radius: 9
                            color: "#0b1a25"
                            border.width: 1
                            border.color: Theme.border
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: String(root.selectedItem.previewUrl || "")
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                                visible: String(root.selectedItem.previewUrl || "").length > 0
                            }

                            Image {
                                anchors.centerIn: parent
                                width: 48
                                height: 48
                                source: root.typeIcon(root.selectedItem.type)
                                opacity: 0.72
                                visible: String(root.selectedItem.previewUrl || "").length === 0
                            }
                        }

                        Text {
                            width: parent.width
                            text: String(root.selectedItem.title || "No media selected")
                            color: Theme.textPrimary
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            wrapMode: Text.Wrap
                        }

                        Text {
                            width: parent.width
                            text: String(root.selectedItem.detail || "")
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                            visible: String(root.selectedItem.detail || "").length > 0
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8

                            Text { text: "TYPE"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: root.typeLabel(root.selectedItem.type); color: Theme.textPrimary; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "MIME"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedItem.mimeType || "—"); color: Theme.textPrimary; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "DATE"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedItem.dateTaken || root.selectedItem.date || "—"); color: Theme.textPrimary; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "CAMERA"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedItem.camera || "—"); color: Theme.textPrimary; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "GPS"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: root.gpsText(root.selectedItem); color: (root.selectedItem.gps || {}).available ? Theme.accent : Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "FACES"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedItem.faceCount || 0); color: Theme.textPrimary; font.pixelSize: 9 }
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Text {
                            text: "LOCAL ANALYSIS"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Row {
                            width: parent.width
                            spacing: 6

                            Repeater {
                                model: [
                                    { label: "GPS", active: Boolean((root.selectedItem.gps || {}).available) },
                                    { label: "OCR", active: String(root.selectedItem.ocrText || "").length > 0 },
                                    { label: "FACES", active: Number(root.selectedItem.faceCount || 0) > 0 },
                                    { label: "TRANSCRIPT", active: String(root.selectedItem.transcript || "").length > 0 }
                                ]

                                delegate: Rectangle {
                                    required property var modelData
                                    width: analysisBadgeText.implicitWidth + 16
                                    height: 24
                                    radius: 6
                                    color: modelData.active ? "#12362f" : Theme.surface
                                    border.width: 1
                                    border.color: modelData.active ? Theme.success : Theme.border
                                    Text {
                                        id: analysisBadgeText
                                        anchors.centerIn: parent
                                        text: String(modelData.label)
                                        color: modelData.active ? Theme.success : Theme.textMuted
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            visible: String(root.selectedItem.ocrText || "").length > 0
                            text: "OCR\n" + String(root.selectedItem.ocrText || "")
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                            maximumLineCount: 8
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            visible: String(root.selectedItem.transcript || "").length > 0
                            text: "TRANSCRIPT\n" + String(root.selectedItem.transcript || "")
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                            maximumLineCount: 10
                            elide: Text.ElideRight
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Text {
                            text: "EXTERNAL MEDIA OSINT"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Text {
                            width: parent.width
                            text: "Reverse-image discovery, image fact checking and web occurrence search will plug into this inspector in the connector stage."
                            color: Theme.textMuted
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        AppButton {
                            width: parent.width
                            text: "Open in Evidence"
                            primary: true
                            enabled: String(root.selectedItem.id || "").length > 0
                            onClicked: desktopBridge.focusWorkspaceRecord(
                                "evidence",
                                String(root.selectedItem.id || "")
                            )
                        }

                        Item { width: 1; height: 8 }
                    }

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }
        }
    }
}
