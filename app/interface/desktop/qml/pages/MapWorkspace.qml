pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var payload: desktopBridge.analysisMapWorkspace || ({})
    property var markers: payload.markers || []
    property var counts: payload.counts || ({})
    property bool showLocations: true
    property bool showPhotoGps: true
    property bool showNearbyPois: true
    property string baseMapMode: mapWebEngineAvailable ? "streets" : "schematic"
    property bool interactiveMapFailed: false
    property bool useInteractiveMap: baseMapMode === "streets"
        && Boolean(mapWebEngineAvailable)
        && !interactiveMapFailed
    property var geoRun: geoBridge.runData || ({})
    property var nearbyPlaces: geoRun.nearbyPlaces || []
    property var weatherData: geoRun.weather || ({})
    property var weatherSummary: weatherData.summary || ({})
    property string selectedMarkerId: ""
    property string selectedMarkerKind: ""
    property var selectedMarker: root.findSelectedMarker()

    function visibleMarkers() {
        var result = []
        for (var i = 0; i < root.markers.length; ++i) {
            var item = root.markers[i]
            var kind = String(item.kind || "")
            if (kind === "location" && !root.showLocations)
                continue
            if (kind === "photo" && !root.showPhotoGps)
                continue
            result.push(item)
        }

        if (Boolean(root.geoRun.hasRun)
                && String(root.geoRun.status || "") !== "failed") {
            result.push({
                id: "geo-query-center",
                kind: "query",
                title: "Live GEO query center",
                detail: "Transient query center · not persisted",
                latitude: root.geoRun.latitude,
                longitude: root.geoRun.longitude,
                source: "Live GEO enrichment",
                transient: true
            })
        }

        if (root.showNearbyPois) {
            for (var j = 0; j < root.nearbyPlaces.length; ++j)
                result.push(root.nearbyPlaces[j])
        }
        return result
    }

    function markerKey(item) {
        return String((item || {}).kind || "")
            + ":"
            + String((item || {}).id || "")
    }

    function findSelectedMarker() {
        var wanted = root.selectedMarkerKind + ":" + root.selectedMarkerId
        var rows = root.visibleMarkers()
        for (var i = 0; i < rows.length; ++i) {
            if (root.markerKey(rows[i]) === wanted)
                return rows[i]
        }
        return ({})
    }

    function ensureMarkerSelection() {
        var rows = root.visibleMarkers()
        if (rows.length === 0) {
            root.selectedMarkerId = ""
            root.selectedMarkerKind = ""
            return
        }

        var wanted = root.selectedMarkerKind + ":" + root.selectedMarkerId
        for (var i = 0; i < rows.length; ++i) {
            if (root.markerKey(rows[i]) === wanted)
                return
        }

        root.selectedMarkerId = String(rows[0].id || "")
        root.selectedMarkerKind = String(rows[0].kind || "")
    }

    function selectMarker(item) {
        root.selectedMarkerId = String((item || {}).id || "")
        root.selectedMarkerKind = String((item || {}).kind || "")
        if (root.useInteractiveMap && interactiveMapLoader.item) {
            interactiveMapLoader.item.focusMarker(
                root.selectedMarkerKind,
                root.selectedMarkerId
            )
        }
    }

    function selectMarkerByKey(kind, markerId) {
        var rows = root.visibleMarkers()
        for (var i = 0; i < rows.length; ++i) {
            if (String(rows[i].kind || "") === String(kind || "")
                    && String(rows[i].id || "") === String(markerId || "")) {
                root.selectMarker(rows[i])
                return
            }
        }
    }

    function useSelectedCoordinates() {
        var item = root.selectedMarker || ({})
        if (item.latitude === undefined || item.latitude === null
                || item.longitude === undefined || item.longitude === null)
            return
        geoLatitudeInput.text = Number(item.latitude).toFixed(7)
        geoLongitudeInput.text = Number(item.longitude).toFixed(7)
    }

    function runGeoEnrichment() {
        var latitude = Number(geoLatitudeInput.text)
        var longitude = Number(geoLongitudeInput.text)
        var radius = parseInt(geoRadiusInput.text)
        if (!isFinite(radius))
            radius = 750
        geoBridge.runEnrichment(
            latitude,
            longitude,
            geoDateInput.text,
            radius
        )
    }

    function weatherValue(key) {
        var value = root.weatherSummary[key]
        if (value === undefined || value === null || String(value).length === 0)
            return "—"
        return String(value)
    }

    function coordinateText(item) {
        if (item.latitude === undefined || item.latitude === null
                || item.longitude === undefined || item.longitude === null)
            return "Coordinates unavailable"

        return Number(item.latitude).toFixed(6)
            + ", "
            + Number(item.longitude).toFixed(6)
    }

    function markerX(item, canvasWidth) {
        return Math.max(
            8,
            Math.min(
                canvasWidth - 24,
                ((Number(item.longitude) + 180.0) / 360.0) * (canvasWidth - 24)
            )
        )
    }

    function markerY(item, canvasHeight) {
        return Math.max(
            8,
            Math.min(
                canvasHeight - 24,
                ((90.0 - Number(item.latitude)) / 180.0) * (canvasHeight - 24)
            )
        )
    }

    Component.onCompleted: root.ensureMarkerSelection()

    Connections {
        target: desktopBridge
        function onChanged() {
            Qt.callLater(root.ensureMarkerSelection)
        }
    }

    Connections {
        target: geoBridge
        function onChanged() {
            Qt.callLater(root.ensureMarkerSelection)
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
                text: "GEO INTELLIGENCE"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.6
            }

            Text {
                x: 1
                y: 18
                text: "Map"
                color: Theme.textPrimary
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }

            Text {
                x: 2
                y: 52
                width: parent.width - 410
                text: root.payload.hasCase
                    ? ("Investigation: " + String(root.payload.caseTitle || "Current investigation"))
                    : "Select an investigation to inspect stored geographic intelligence."
                color: Theme.textSecondary
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            Row {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                spacing: 8

                Rectangle {
                    width: mappedBadge.implicitWidth + 20
                    height: 28
                    radius: 7
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: mappedBadge
                        anchors.centerIn: parent
                        text: String(root.counts.mapped || 0) + " mapped"
                        color: Theme.textSecondary
                        font.pixelSize: 9
                    }
                }

                Rectangle {
                    width: photoBadge.implicitWidth + 20
                    height: 28
                    radius: 7
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: photoBadge
                        anchors.centerIn: parent
                        text: String(root.counts.photoGps || 0) + " photo GPS"
                        color: Theme.textSecondary
                        font.pixelSize: 9
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 42
            radius: 8
            color: Theme.surface
            border.width: 1
            border.color: Theme.border

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 18

                Text {
                    text: "LAYERS"
                    color: Theme.textMuted
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.0
                    anchors.verticalCenter: parent.verticalCenter
                }

                CheckBox {
                    text: "Locations"
                    checked: root.showLocations
                    onToggled: {
                        root.showLocations = checked
                        root.ensureMarkerSelection()
                    }
                }

                CheckBox {
                    text: "Photo GPS"
                    checked: root.showPhotoGps
                    onToggled: {
                        root.showPhotoGps = checked
                        root.ensureMarkerSelection()
                    }
                }

                CheckBox {
                    text: "Nearby POI"
                    checked: root.showNearbyPois
                    enabled: root.nearbyPlaces.length > 0
                    onToggled: {
                        root.showNearbyPois = checked
                        root.ensureMarkerSelection()
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                Text {
                    text: "BASE MAP"
                    color: Theme.textMuted
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }

                Rectangle {
                    width: 82
                    height: 26
                    radius: 6
                    color: root.baseMapMode === "streets" ? Theme.accentSoft : Theme.surface
                    border.width: 1
                    border.color: root.baseMapMode === "streets" ? Theme.accent : Theme.border

                    Text {
                        anchors.centerIn: parent
                        text: "Streets"
                        color: root.baseMapMode === "streets" ? Theme.textPrimary : Theme.textSecondary
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: Boolean(mapWebEngineAvailable)
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            root.interactiveMapFailed = false
                            root.baseMapMode = "streets"
                        }
                    }

                    ToolTip.visible: !Boolean(mapWebEngineAvailable) && streetsHover.containsMouse
                    ToolTip.text: "Qt WebEngine is unavailable; using the local schematic."
                    MouseArea {
                        id: streetsHover
                        anchors.fill: parent
                        enabled: !Boolean(mapWebEngineAvailable)
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }
                }

                Rectangle {
                    width: 92
                    height: 26
                    radius: 6
                    color: root.baseMapMode === "schematic" ? Theme.accentSoft : Theme.surface
                    border.width: 1
                    border.color: root.baseMapMode === "schematic" ? Theme.accent : Theme.border

                    Text {
                        anchors.centerIn: parent
                        text: "Schematic"
                        color: root.baseMapMode === "schematic" ? Theme.textPrimary : Theme.textSecondary
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.baseMapMode = "schematic"
                    }
                }

                Rectangle {
                    width: 104
                    height: 26
                    radius: 6
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    opacity: 0.58

                    Text {
                        anchors.centerIn: parent
                        text: "Satellite · next"
                        color: Theme.textMuted
                        font.pixelSize: 8
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
                title: "Geographic Canvas"
                subtitle: root.useInteractiveMap
                    ? "Interactive streets · pan · zoom · clusters · live investigation layers"
                    : "Offline-safe schematic fallback"
                iconSource: "../../assets/icons/pin_purple.svg"

                Item {
                    id: mapCanvas
                    anchors.fill: parent
                    anchors.margins: 12
                    clip: true

                    Rectangle {
                        anchors.fill: parent
                        radius: 10
                        color: "#081722"
                        border.width: 1
                        border.color: Theme.border
                    }

                    Loader {
                        id: interactiveMapLoader
                        anchors.fill: parent
                        active: root.useInteractiveMap
                        source: active ? "../components/InteractiveMapView.qml" : ""

                        onLoaded: {
                            item.markers = Qt.binding(function() {
                                return root.visibleMarkers()
                            })
                            item.selectedMarkerId = Qt.binding(function() {
                                return root.selectedMarkerId
                            })
                            item.selectedMarkerKind = Qt.binding(function() {
                                return root.selectedMarkerKind
                            })
                        }
                    }

                    Connections {
                        target: interactiveMapLoader.item
                        function onMarkerSelected(kind, markerId) {
                            root.selectMarkerByKey(kind, markerId)
                        }
                        function onMapUnavailable(message) {
                            root.interactiveMapFailed = true
                            root.baseMapMode = "schematic"
                        }
                    }

                    Item {
                        id: schematicMap
                        anchors.fill: parent
                        visible: !root.useInteractiveMap

                        Item {
                            id: projection
                            anchors.centerIn: parent
                            width: Math.max(120, parent.width - 20)
                            height: Math.max(
                                60,
                                Math.min(
                                    parent.height - 20,
                                    width / 2
                                )
                            )

                            Image {
                                anchors.fill: parent
                                source: "../../assets/images/world_map_dots.svg"
                                fillMode: Image.Stretch
                                opacity: 0.54
                                smooth: true
                            }

                            Repeater {
                                model: root.visibleMarkers()

                                delegate: Rectangle {
                                    id: geoMarker
                                    required property var modelData
                                    width: markerMouse.containsMouse || selected ? 18 : 14
                                    height: width
                                    radius: width / 2
                                    property bool selected: root.selectedMarkerId === String(modelData.id || "")
                                        && root.selectedMarkerKind === String(modelData.kind || "")
                                    x: root.markerX(modelData, projection.width) - width / 2
                                    y: root.markerY(modelData, projection.height) - height / 2
                                    color: String(modelData.kind || "") === "photo"
                                        ? "#e5a84b"
                                        : (String(modelData.kind || "") === "poi"
                                            ? "#49c5d8"
                                            : (String(modelData.kind || "") === "query"
                                                ? "#36cfa1"
                                                : "#c78cf4"))
                                    border.width: 2
                                    border.color: selected ? Theme.textPrimary : "#d7e3ec"
                                    z: selected ? 5 : 2

                                    Behavior on width { NumberAnimation { duration: 90 } }

                                    MouseArea {
                                        id: markerMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.selectMarker(geoMarker.modelData)
                                    }

                                    ToolTip.visible: markerMouse.containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: String(modelData.title || "Location")
                                        + "\n"
                                        + root.coordinateText(modelData)
                                }
                            }
                        }

                        Column {
                            anchors.centerIn: parent
                            visible: root.visibleMarkers().length === 0
                            width: Math.min(500, parent.width - 80)
                            spacing: 10

                            Image {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 42
                                height: 42
                                source: "../../assets/icons/pin_purple.svg"
                                opacity: 0.6
                            }

                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: root.payload.hasCase ? "No mapped coordinates yet" : "No investigation selected"
                                color: Theme.textPrimary
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                            }

                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.Wrap
                                text: root.payload.hasCase
                                    ? "LOCATION entities, live POI and GPS-tagged images will appear here automatically."
                                    : "Select an investigation before opening the Map workspace."
                                color: Theme.textSecondary
                                font.pixelSize: 10
                            }
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 12
                            width: legendRow.implicitWidth + 20
                            height: 30
                            radius: 7
                            color: "#d9081722"
                            border.width: 1
                            border.color: Theme.border

                            Row {
                                id: legendRow
                                anchors.centerIn: parent
                                spacing: 12

                                Row {
                                    spacing: 5
                                    Rectangle { width: 9; height: 9; radius: 5; color: "#c78cf4"; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Location"; color: Theme.textSecondary; font.pixelSize: 8 }
                                }

                                Row {
                                    spacing: 5
                                    Rectangle { width: 9; height: 9; radius: 5; color: "#e5a84b"; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Photo GPS"; color: Theme.textSecondary; font.pixelSize: 8 }
                                }

                                Row {
                                    spacing: 5
                                    visible: root.nearbyPlaces.length > 0
                                    Rectangle { width: 9; height: 9; radius: 5; color: "#49c5d8"; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Live POI"; color: Theme.textSecondary; font.pixelSize: 8 }
                                }
                            }
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.top: parent.top
                        anchors.topMargin: 12
                        visible: root.interactiveMapFailed
                        width: fallbackText.implicitWidth + 18
                        height: 28
                        radius: 7
                        color: "#d95a261f"
                        border.width: 1
                        border.color: Theme.warning

                        Text {
                            id: fallbackText
                            anchors.centerIn: parent
                            text: "Interactive basemap unavailable · schematic fallback"
                            color: Theme.warning
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }

            Panel {
                Layout.preferredWidth: 360
                Layout.maximumWidth: 400
                Layout.fillHeight: true
                title: "Location Inspector"
                subtitle: String(root.visibleMarkers().length) + " visible marker(s)"
                iconSource: "../../assets/icons/search.svg"

                Flickable {
                    anchors.fill: parent
                    clip: true
                    contentWidth: width
                    contentHeight: locationInspectorColumn.height + 20
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: locationInspectorColumn
                        x: 14
                        width: parent.width - 28
                        spacing: 10

                        Item { width: 1; height: 2 }

                        Rectangle {
                            width: parent.width
                            height: 122
                            radius: 9
                            color: "#0b1a25"
                            border.width: 1
                            border.color: Theme.border
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: String(root.selectedMarker.previewUrl || "")
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: false
                                visible: String(root.selectedMarker.previewUrl || "").length > 0
                            }

                            Image {
                                anchors.centerIn: parent
                                width: 38
                                height: 38
                                source: "../../assets/icons/pin_purple.svg"
                                opacity: 0.72
                                visible: String(root.selectedMarker.previewUrl || "").length === 0
                            }
                        }

                        Text {
                            width: parent.width
                            text: String(root.selectedMarker.title || "No marker selected")
                            color: Theme.textPrimary
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            wrapMode: Text.Wrap
                        }

                        Text {
                            width: parent.width
                            text: root.coordinateText(root.selectedMarker)
                            color: Theme.accent
                            font.pixelSize: 10
                        }

                        Text {
                            width: parent.width
                            text: String(root.selectedMarker.detail || "")
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                            visible: String(root.selectedMarker.detail || "").length > 0
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8

                            Text { text: "LAYER"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedMarker.kind || "—").toUpperCase(); color: Theme.textPrimary; font.pixelSize: 9 }
                            Text { text: "SOURCE"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text { Layout.fillWidth: true; text: String(root.selectedMarker.source || "—"); color: Theme.textPrimary; font.pixelSize: 9; elide: Text.ElideRight }
                            Text { text: "ALTITUDE"; color: Theme.textMuted; font.pixelSize: 8 }
                            Text {
                                Layout.fillWidth: true
                                text: root.selectedMarker.altitude === undefined || root.selectedMarker.altitude === null
                                    ? "—"
                                    : String(root.selectedMarker.altitude) + " m"
                                color: Theme.textPrimary
                                font.pixelSize: 9
                            }
                        }

                        AppButton {
                            width: parent.width
                            visible: String(root.selectedMarker.evidenceId || "").length > 0
                            text: "Open source Evidence"
                            primary: true
                            onClicked: desktopBridge.focusWorkspaceRecord(
                                "evidence",
                                String(root.selectedMarker.evidenceId || "")
                            )
                        }

                        AppButton {
                            width: parent.width
                            visible: String(root.selectedMarker.sourceUrl || "").length > 0
                            text: "Open source page"
                            onClicked: desktopBridge.openExternalUrl(
                                String(root.selectedMarker.sourceUrl || "")
                            )
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Text {
                            text: "LIVE GEO ENRICHMENT"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Text {
                            width: parent.width
                            text: "Overpass / OpenStreetMap nearby objects + Open-Meteo historical weather. Live results are transient and are not persisted."
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        GridLayout {
                            width: parent.width
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8

                            AppTextField {
                                id: geoLatitudeInput
                                Layout.fillWidth: true
                                placeholderText: "Latitude"
                                text: ""
                            }

                            AppTextField {
                                id: geoLongitudeInput
                                Layout.fillWidth: true
                                placeholderText: "Longitude"
                                text: ""
                            }

                            AppTextField {
                                id: geoRadiusInput
                                Layout.fillWidth: true
                                placeholderText: "Radius m"
                                text: "750"
                                inputMethodHints: Qt.ImhDigitsOnly
                            }

                            AppTextField {
                                id: geoDateInput
                                Layout.fillWidth: true
                                placeholderText: "YYYY-MM-DD (optional)"
                                text: ""
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 8

                            AppButton {
                                width: (parent.width - 8) * 0.38
                                text: "Use selected"
                                enabled: root.selectedMarker.latitude !== undefined
                                    && root.selectedMarker.latitude !== null
                                    && root.selectedMarker.longitude !== undefined
                                    && root.selectedMarker.longitude !== null
                                    && !geoBridge.busy
                                onClicked: root.useSelectedCoordinates()
                            }

                            AppButton {
                                width: (parent.width - 8) * 0.62
                                text: geoBridge.busy ? "Enriching…" : "Run GEO Enrichment"
                                primary: true
                                enabled: !geoBridge.busy
                                    && geoLatitudeInput.text.trim().length > 0
                                    && geoLongitudeInput.text.trim().length > 0
                                onClicked: root.runGeoEnrichment()
                            }
                        }

                        Text {
                            width: parent.width
                            visible: String(geoBridge.message || "").length > 0
                            text: String(geoBridge.message || "")
                            color: String(root.geoRun.status || "") === "failed"
                                ? Theme.danger
                                : Theme.textSecondary
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        Column {
                            width: parent.width
                            visible: Boolean(root.geoRun.hasRun)
                            spacing: 4

                            Repeater {
                                model: root.geoRun.providers || []

                                delegate: Text {
                                    required property var modelData
                                    width: parent.width
                                    visible: String(modelData.error || "").length > 0
                                    text: String(modelData.source || "provider")
                                        + " · "
                                        + String(modelData.status || "unknown").toUpperCase()
                                        + " · "
                                        + String(modelData.error || "")
                                    color: String(modelData.status || "") === "failed"
                                        ? Theme.danger
                                        : Theme.warning
                                    font.pixelSize: 8
                                    wrapMode: Text.Wrap
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            visible: Boolean(root.geoRun.hasRun)
                            spacing: 6

                            Rectangle {
                                width: nearbyCountText.implicitWidth + 16
                                height: 24
                                radius: 6
                                color: Theme.surface
                                border.width: 1
                                border.color: Theme.border
                                Text {
                                    id: nearbyCountText
                                    anchors.centerIn: parent
                                    text: String((root.geoRun.summary || {}).nearbyPlaces || 0) + " POI"
                                    color: Theme.textSecondary
                                    font.pixelSize: 8
                                }
                            }

                            Rectangle {
                                width: weatherBadgeText.implicitWidth + 16
                                height: 24
                                radius: 6
                                color: Boolean((root.geoRun.summary || {}).weatherAvailable)
                                    ? "#12362f"
                                    : Theme.surface
                                border.width: 1
                                border.color: Boolean((root.geoRun.summary || {}).weatherAvailable)
                                    ? Theme.success
                                    : Theme.border
                                Text {
                                    id: weatherBadgeText
                                    anchors.centerIn: parent
                                    text: Boolean((root.geoRun.summary || {}).weatherAvailable)
                                        ? "WEATHER READY"
                                        : "WEATHER SKIPPED"
                                    color: Boolean((root.geoRun.summary || {}).weatherAvailable)
                                        ? Theme.success
                                        : Theme.textMuted
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }
                            }

                            Rectangle {
                                width: 94
                                height: 24
                                radius: 6
                                color: Theme.surface
                                border.width: 1
                                border.color: Theme.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "TRANSIENT"
                                    color: Theme.warning
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: weatherColumn.visible ? weatherColumn.height + 20 : 0
                            visible: weatherColumn.visible
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            Column {
                                id: weatherColumn
                                x: 10
                                y: 10
                                width: parent.width - 20
                                visible: Boolean(root.weatherData.available)
                                spacing: 5

                                Text {
                                    text: "HISTORICAL WEATHER · " + String(root.weatherSummary.date || "")
                                    color: Theme.textPrimary
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    width: parent.width
                                    text: "Temperature "
                                        + root.weatherValue("temperature_2m_min")
                                        + " → "
                                        + root.weatherValue("temperature_2m_max")
                                        + " °C · precipitation "
                                        + root.weatherValue("precipitation_sum")
                                        + " mm"
                                    color: Theme.textSecondary
                                    font.pixelSize: 9
                                    wrapMode: Text.Wrap
                                }

                                Text {
                                    width: parent.width
                                    text: "Sunrise "
                                        + String(root.weatherSummary.sunrise || "—")
                                        + " · sunset "
                                        + String(root.weatherSummary.sunset || "—")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    wrapMode: Text.Wrap
                                }
                            }
                        }

                        Column {
                            width: parent.width
                            visible: root.nearbyPlaces.length > 0
                            spacing: 5

                            Text {
                                text: "NEARBY OSM OBJECTS"
                                color: Theme.textMuted
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.0
                            }

                            Repeater {
                                model: root.nearbyPlaces.slice(0, 8)

                                delegate: Rectangle {
                                    id: poiRow
                                    required property var modelData
                                    width: parent.width
                                    height: 44
                                    radius: 6
                                    color: poiMouse.containsMouse ? Theme.surfaceHover : Theme.surface
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        x: 9
                                        y: 7
                                        width: parent.width - 18
                                        text: String(poiRow.modelData.title || "OSM object")
                                        color: Theme.textPrimary
                                        font.pixelSize: 9
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        x: 9
                                        y: 24
                                        width: parent.width - 18
                                        text: String(poiRow.modelData.category || "poi").replace(/_/g, " ")
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        elide: Text.ElideRight
                                    }

                                    MouseArea {
                                        id: poiMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.selectMarker(poiRow.modelData)
                                    }
                                }
                            }
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.divider }

                        Text {
                            text: "SATELLITE"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Rectangle {
                            width: parent.width
                            height: 76
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            Text {
                                anchors.fill: parent
                                anchors.margins: 12
                                text: "Satellite imagery is not connected yet. Copernicus/Sentinel will become a base layer here instead of a separate application page."
                                color: Theme.textSecondary
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text {
                            visible: Number(root.counts.unmapped || 0) > 0
                            width: parent.width
                            text: String(root.counts.unmapped || 0)
                                + " stored location/address item(s) have no coordinates and are not plotted."
                            color: Theme.warning
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        Item { width: 1; height: 8 }
                    }

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }
        }
    }
}
