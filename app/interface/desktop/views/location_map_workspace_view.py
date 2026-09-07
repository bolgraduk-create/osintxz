"""
Location map workspace view.

Interactive investigation map for geographic entities.

Responsibilities:

- render interactive map inside desktop UI
- display investigation LOCATION entities
- support street and satellite basemaps
- focus selected locations
- display selected location details
- expose map interactions through Qt signals
- prepare foundation for markers, links and drawing tools

Does NOT:

- access database directly
- create or update entities
- commit transactions
- perform reverse geocoding
- own investigation business logic
"""

from __future__ import annotations

import json

from typing import Any

from PySide6.QtCore import (
    QObject,
    QSize,
    Qt,
    Signal,
    Slot,
)

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QColorDialog,
    QLineEdit,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
)

from PySide6.QtGui import (
    QColor,
    QIcon,
    QPixmap,
)

from PySide6.QtWebChannel import (
    QWebChannel,
)

from PySide6.QtWebEngineWidgets import (
    QWebEngineView,
)


class LocationMapBridge(
    QObject,
):
    """
    Bridge between Leaflet JavaScript and Qt/Python.
    """

    map_clicked = Signal(
        float,
        float,
    )

    marker_clicked = Signal(
        str
    )

    map_ready = Signal()

    # ==========================================================
    # JavaScript -> Python
    # ==========================================================

    @Slot(float, float)
    def on_map_clicked(
        self,
        latitude: float,
        longitude: float,
    ) -> None:

        self.map_clicked.emit(
            latitude,
            longitude,
        )

    @Slot(str)
    def on_marker_clicked(
        self,
        location_id: str,
    ) -> None:

        self.marker_clicked.emit(
            location_id
        )

    @Slot()
    def on_map_ready(
        self,
    ) -> None:

        self.map_ready.emit()


class LocationMapWorkspaceView(
    QWidget,
):
    """
    Geographic investigation workspace.

    The map is a visualization layer only.
    Persistent location data remains in application services.
    """

    marker_selected = Signal(
        str
    )

    map_position_requested = Signal(
        float,
        float,
    )

    add_marker_requested = Signal(
        float,
        float,
    )

    location_edit_requested = Signal(
        str,
        str,
        str,
        str,
    )

    location_photos_requested = Signal(
    str
    )

    attach_location_photo_requested = Signal(
        str
    )

    detach_location_photo_requested = Signal(
        str,
        str,
    )

    open_location_photo_requested = Signal(
        str
    )

    connect_locations_requested = Signal()

    # ==========================================================
    # Defaults
    # ==========================================================

    DEFAULT_LATITUDE = 48.0
    DEFAULT_LONGITUDE = 30.0
    DEFAULT_ZOOM = 5

    STREET_LAYER = "street"
    SATELLITE_LAYER = "satellite"

    # ==========================================================
    # Initialization
    # ==========================================================

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.setObjectName(
            "LocationMapWorkspaceView"
        )

        self._locations: list[
            dict[str, Any]
        ] = []

        self._selected_location_id: (
            str
            | None
        ) = None

        self._location_photos: list[
            dict[str, Any]
        ] = []

        self._selected_photo_evidence_id: (
            str
            | None
        ) = None

        self._editing_location = False

        self._selected_marker_color = (
            "#e072c4"
        )

        self._map_ready = False

        self._pending_focus: (
            tuple[
                float,
                float,
                int,
            ]
            | None
        ) = None

        self._setup_ui()

        self._setup_web_channel()

        self._clear_location_details()

        self._load_map()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.setSpacing(
            8
        )

        # ------------------------------------------------------
        # Toolbar
        # ------------------------------------------------------

        self.toolbar = QWidget(
            self
        )

        self.toolbar.setObjectName(
            "LocationMapToolbar"
        )

        toolbar_layout = QHBoxLayout(
            self.toolbar
        )

        toolbar_layout.setContentsMargins(
            12,
            8,
            12,
            8,
        )

        toolbar_layout.setSpacing(
            8
        )

        self.map_label = QLabel(
            "Map",
            self.toolbar,
        )

        self.map_label.setObjectName(
            "LocationMapTitle"
        )

        toolbar_layout.addWidget(
            self.map_label
        )

        toolbar_layout.addSpacing(
            8
        )

        self.layer_combo = QComboBox(
            self.toolbar
        )

        self.layer_combo.addItem(
            "Satellite",
            self.SATELLITE_LAYER,
        )

        self.layer_combo.addItem(
            "Street",
            self.STREET_LAYER,
        )

        self.layer_combo.setCurrentIndex(
            0
        )

        toolbar_layout.addWidget(
            self.layer_combo
        )

        self.add_marker_button = QPushButton(
            "+ Marker",
            self.toolbar,
        )

        toolbar_layout.addWidget(
            self.add_marker_button
        )

        self.connect_button = QPushButton(
            "Connect",
            self.toolbar,
        )

        toolbar_layout.addWidget(
            self.connect_button
        )

        self.fit_button = QPushButton(
            "Fit locations",
            self.toolbar,
        )

        toolbar_layout.addWidget(
            self.fit_button
        )

        toolbar_layout.addStretch(
            1
        )

        self.location_count_label = QLabel(
            "0 locations",
            self.toolbar,
        )

        toolbar_layout.addWidget(
            self.location_count_label
        )

        self.main_layout.addWidget(
            self.toolbar
        )

        # ------------------------------------------------------
        # Main splitter
        # ------------------------------------------------------

        self.content_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.content_splitter.setObjectName(
            "LocationMapSplitter"
        )

        self.content_splitter.setChildrenCollapsible(
            False
        )

        # ------------------------------------------------------
        # Web map
        # ------------------------------------------------------

        self.web_view = QWebEngineView(
            self.content_splitter
        )

        self.web_view.setObjectName(
            "LocationMapWebView"
        )

        self.content_splitter.addWidget(
            self.web_view
        )

        # ------------------------------------------------------
        # Location details panel
        # ------------------------------------------------------

        self.details_panel = self._create_details_panel()

        self.content_splitter.addWidget(
            self.details_panel
        )

        self.content_splitter.setStretchFactor(
            0,
            1,
        )

        self.content_splitter.setStretchFactor(
            1,
            0,
        )

        self.content_splitter.setSizes(
            [
                1000,
                330,
            ]
        )

        self.main_layout.addWidget(
            self.content_splitter,
            1,
        )

        # ------------------------------------------------------
        # Signals
        # ------------------------------------------------------

        self.layer_combo.currentIndexChanged.connect(
            self._on_layer_changed
        )

        self.fit_button.clicked.connect(
            self.fit_locations
        )

        self.connect_button.clicked.connect(
            self.connect_locations_requested.emit
        )

        self.edit_location_button.clicked.connect(
            self._start_location_edit
        )

        self.cancel_location_button.clicked.connect(
            self._cancel_location_edit
        )

        self.save_location_button.clicked.connect(
            self._save_location_edit
        )

        self.edit_color_button.clicked.connect(
            self._choose_marker_color
        )

        self.location_photos_list.itemSelectionChanged.connect(
            self._on_location_photo_selection_changed
        )

        self.location_photos_list.itemDoubleClicked.connect(
            self._open_location_photo
        )

        self.attach_photo_button.clicked.connect(
            self._request_attach_location_photo
        )

        self.remove_photo_button.clicked.connect(
            self._request_detach_location_photo
        )

    def _create_details_panel(
        self,
    ) -> QWidget:
        """
        Create right-side location information panel.
        """

        panel = QFrame(
            self
        )

        panel.setObjectName(
            "LocationDetailsPanel"
        )

        panel.setMinimumWidth(
            280
        )

        panel.setMaximumWidth(
            430
        )

        outer_layout = QVBoxLayout(
            panel
        )

        outer_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        outer_layout.setSpacing(
            10
        )

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        self.details_title = QLabel(
            "Location details",
            panel,
        )

        self.details_title.setObjectName(
            "LocationDetailsTitle"
        )

        outer_layout.addWidget(
            self.details_title
        )

        self.details_status_label = QLabel(
            "Select a marker on the map.",
            panel,
        )

        self.details_status_label.setWordWrap(
            True
        )

        self.details_status_label.setObjectName(
            "LocationDetailsStatus"
        )

        outer_layout.addWidget(
            self.details_status_label
        )

        # ------------------------------------------------------
        # Scrollable content
        # ------------------------------------------------------

        self.details_scroll = QScrollArea(
            panel
        )

        self.details_scroll.setWidgetResizable(
            True
        )

        self.details_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.details_content = QWidget(
            self.details_scroll
        )

        self.details_content.setObjectName(
            "LocationDetailsContent"
        )

        details_layout = QVBoxLayout(
            self.details_content
        )

        details_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        details_layout.setSpacing(
            12
        )

        # ------------------------------------------------------
        # Name
        # ------------------------------------------------------

        self.location_name_label = QLabel(
            "—",
            self.details_content,
        )

        self.location_name_label.setObjectName(
            "LocationSelectedName"
        )

        self.location_name_label.setWordWrap(
            True
        )

        details_layout.addWidget(
            self.location_name_label
        )

        self.edit_location_button = QPushButton(
            "Edit",
            self.details_content,
        )

        self.edit_location_button.setEnabled(
            False
        )

        details_layout.addWidget(
            self.edit_location_button
        )

        # ------------------------------------------------------
        # Core fields
        # ------------------------------------------------------

        information_widget = QWidget(
            self.details_content
        )

        information_layout = QFormLayout(
            information_widget
        )

        information_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        information_layout.setHorizontalSpacing(
            12
        )

        information_layout.setVerticalSpacing(
            8
        )

        self.latitude_value = QLabel(
            "—"
        )

        self.longitude_value = QLabel(
            "—"
        )

        self.altitude_value = QLabel(
            "—"
        )

        self.location_id_value = QLabel(
            "—"
        )

        self.source_type_value = QLabel(
            "—"
        )

        self.source_evidence_value = QLabel(
            "—"
        )

        for label in (
            self.latitude_value,
            self.longitude_value,
            self.altitude_value,
            self.location_id_value,
            self.source_type_value,
            self.source_evidence_value,
        ):

            label.setWordWrap(
                True
            )

            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

        information_layout.addRow(
            "Latitude:",
            self.latitude_value,
        )

        information_layout.addRow(
            "Longitude:",
            self.longitude_value,
        )

        information_layout.addRow(
            "Altitude:",
            self.altitude_value,
        )

        information_layout.addRow(
            "Location ID:",
            self.location_id_value,
        )

        information_layout.addRow(
            "Source:",
            self.source_type_value,
        )

        information_layout.addRow(
            "Evidence:",
            self.source_evidence_value,
        )

        details_layout.addWidget(
            information_widget
        )

        # ------------------------------------------------------
        # Description
        # ------------------------------------------------------

        description_title = QLabel(
            "Description",
            self.details_content,
        )

        description_title.setObjectName(
            "LocationDescriptionTitle"
        )

        details_layout.addWidget(
            description_title
        )

        self.description_text = QTextEdit(
            self.details_content
        )

        self.description_text.setReadOnly(
            True
        )

        self.description_text.setMinimumHeight(
            140
        )

        self.description_text.setPlaceholderText(
            "No description."
        )

        details_layout.addWidget(
            self.description_text
        )

        self.edit_widget = QWidget(
            self.details_content
        )

        edit_layout = QVBoxLayout(
            self.edit_widget
        )

        edit_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        edit_layout.setSpacing(
            8
        )

        edit_form = QFormLayout()

        self.edit_name_input = QLineEdit(
            self.edit_widget
        )

        edit_form.addRow(
            "Name:",
            self.edit_name_input,
        )

        self.edit_description_input = QTextEdit(
            self.edit_widget
        )

        self.edit_description_input.setMinimumHeight(
            110
        )

        edit_form.addRow(
            "Description:",
            self.edit_description_input,
        )

        edit_layout.addLayout(
            edit_form
        )

        color_layout = QHBoxLayout()

        self.edit_color_value = QLineEdit(
            self.edit_widget
        )

        self.edit_color_value.setReadOnly(
            True
        )

        self.edit_color_button = QPushButton(
            "Choose color",
            self.edit_widget,
        )

        color_layout.addWidget(
            self.edit_color_value,
            1,
        )

        color_layout.addWidget(
            self.edit_color_button
        )

        edit_layout.addLayout(
            color_layout
        )

        actions_layout = QHBoxLayout()

        self.save_location_button = QPushButton(
            "Save",
            self.edit_widget,
        )

        self.cancel_location_button = QPushButton(
            "Cancel",
            self.edit_widget,
        )

        actions_layout.addWidget(
            self.save_location_button
        )

        actions_layout.addWidget(
            self.cancel_location_button
        )

        edit_layout.addLayout(
            actions_layout
        )

        self.edit_widget.setVisible(
            False
        )

        details_layout.addWidget(
            self.edit_widget
        )

        # ------------------------------------------------------
        # Photos
        # ------------------------------------------------------

        photos_title = QLabel(
            "Photos",
            self.details_content,
        )

        photos_title.setObjectName(
            "LocationPhotosTitle"
        )

        details_layout.addWidget(
            photos_title
        )

        self.photos_status_label = QLabel(
            "Select a location to load photos.",
            self.details_content,
        )

        self.photos_status_label.setWordWrap(
            True
        )

        details_layout.addWidget(
            self.photos_status_label
        )

        self.location_photos_list = QListWidget(
            self.details_content
        )

        self.location_photos_list.setObjectName(
            "LocationPhotosList"
        )

        self.location_photos_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.location_photos_list.setResizeMode(
            QListWidget.ResizeMode.Adjust
        )

        self.location_photos_list.setMovement(
            QListWidget.Movement.Static
        )

        self.location_photos_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.location_photos_list.setIconSize(
            QSize(
                140,
                100,
            )
        )

        self.location_photos_list.setGridSize(
            QSize(
                170,
                145,
            )
        )

        self.location_photos_list.setMinimumHeight(
            165
        )

        details_layout.addWidget(
            self.location_photos_list
        )

        photo_actions_layout = QHBoxLayout()

        self.attach_photo_button = QPushButton(
            "+ Attach Photo",
            self.details_content,
        )

        self.attach_photo_button.setEnabled(
            False
        )

        self.remove_photo_button = QPushButton(
            "Remove",
            self.details_content,
        )

        self.remove_photo_button.setEnabled(
            False
        )

        photo_actions_layout.addWidget(
            self.attach_photo_button
        )

        photo_actions_layout.addWidget(
            self.remove_photo_button
        )

        details_layout.addLayout(
            photo_actions_layout
        )

        # ------------------------------------------------------
        # Provenance
        # ------------------------------------------------------

        provenance_title = QLabel(
            "Provenance",
            self.details_content,
        )

        provenance_title.setObjectName(
            "LocationProvenanceTitle"
        )

        details_layout.addWidget(
            provenance_title
        )

        self.provenance_text = QTextEdit(
            self.details_content
        )

        self.provenance_text.setReadOnly(
            True
        )

        self.provenance_text.setMinimumHeight(
            100
        )

        self.provenance_text.setPlaceholderText(
            "No provenance information."
        )

        details_layout.addWidget(
            self.provenance_text
        )

        details_layout.addStretch(
            1
        )

        self.details_scroll.setWidget(
            self.details_content
        )

        outer_layout.addWidget(
            self.details_scroll,
            1,
        )

        return panel

    # ==========================================================
    # WebChannel
    # ==========================================================

    def _setup_web_channel(
        self,
    ) -> None:

        self.bridge = LocationMapBridge(
            self
        )

        self.channel = QWebChannel(
            self.web_view.page()
        )

        self.channel.registerObject(
            "locationBridge",
            self.bridge,
        )

        self.web_view.page().setWebChannel(
            self.channel
        )

        self.bridge.marker_clicked.connect(
            self._on_marker_selected
        )

        self.bridge.map_clicked.connect(
            self.map_position_requested.emit
        )

        self.bridge.map_ready.connect(
            self._on_map_ready
        )

    # ==========================================================
    # Map loading
    # ==========================================================

    def _load_map(
        self,
    ) -> None:

        html = self._build_map_html()

        self.web_view.setHtml(
            html
        )

    @staticmethod
    def _build_map_html(
    ) -> str:

        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    >

    <script
        src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">
    </script>

    <script
        src="qrc:///qtwebchannel/qwebchannel.js">
    </script>

    <style>

        html,
        body,
        #map {
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
            background: #11151b;
        }

        .leaflet-container {
            background: #11151b;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }

        .location-marker {
            width: 18px;
            height: 18px;

            border-radius: 50%;

            background: #e072c4;

            border: 3px solid #ffffff;

            box-shadow:
                0 2px 8px
                rgba(0, 0, 0, 0.55);
        }

        .location-popup {
            min-width: 180px;
        }

        .location-popup-title {
            font-weight: 700;
            margin-bottom: 6px;
        }

        .location-popup-coordinates {
            font-size: 12px;
            opacity: 0.75;
        }

    </style>
</head>

<body>

<div id="map"></div>

<script>

    let qtBridge = null;

    let activeLayerName = "satellite";

    const markers = {};

    const markerGroup = L.featureGroup();

    // ========================================================
    // Base map
    // ========================================================

    const map = L.map(
        "map",
        {
            zoomControl: true,
            preferCanvas: true
        }
    ).setView(
        [48.0, 30.0],
        5
    );

    // --------------------------------------------------------
    // Street layer
    // --------------------------------------------------------

    const streetLayer = L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                '&copy; OpenStreetMap contributors'
        }
    );

    // --------------------------------------------------------
    // Satellite layer
    // --------------------------------------------------------

    const satelliteLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/" +
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 19,

            attribution:
                "Tiles &copy; Esri"
        }
    );

    satelliteLayer.addTo(
        map
    );

    markerGroup.addTo(
        map
    );

    // ========================================================
    // Qt WebChannel
    // ========================================================

    new QWebChannel(
        qt.webChannelTransport,

        function(channel) {

            qtBridge =
                channel.objects.locationBridge;

            if (
                qtBridge
                && qtBridge.on_map_ready
            ) {

                qtBridge.on_map_ready();

            }

        }
    );

    // ========================================================
    // Map click
    // ========================================================

    map.on(
        "click",

        function(event) {

            if (
                !qtBridge
                || !qtBridge.on_map_clicked
            ) {

                return;

            }

            qtBridge.on_map_clicked(
                event.latlng.lat,
                event.latlng.lng
            );

        }
    );

    // ========================================================
    // Helpers
    // ========================================================

    function escapeHtml(value) {

        const element =
            document.createElement("div");

        element.textContent =
            value == null
                ? ""
                : String(value);

        return element.innerHTML;

    }


    function createMarkerIcon(
        color
    ) {

        const safeColor =
            color || "#e072c4";

        return L.divIcon(
            {
                className: "",

                html:
                    '<div class="location-marker" ' +
                    'style="background:' +
                    safeColor +
                    '"></div>',

                iconSize: [
                    24,
                    24
                ],

                iconAnchor: [
                    12,
                    12
                ],

                popupAnchor: [
                    0,
                    -12
                ]
            }
        );

    }

    // ========================================================
    // Public Python -> JS functions
    // ========================================================

    window.setMapLayer =
        function(layerName) {

            if (
                map.hasLayer(
                    streetLayer
                )
            ) {

                map.removeLayer(
                    streetLayer
                );

            }

            if (
                map.hasLayer(
                    satelliteLayer
                )
            ) {

                map.removeLayer(
                    satelliteLayer
                );

            }

            if (
                layerName === "street"
            ) {

                streetLayer.addTo(
                    map
                );

                activeLayerName =
                    "street";

            }
            else {

                satelliteLayer.addTo(
                    map
                );

                activeLayerName =
                    "satellite";

            }

        };


    window.clearLocations =
        function() {

            markerGroup.clearLayers();

            Object.keys(
                markers
            ).forEach(
                function(key) {

                    delete markers[
                        key
                    ];

                }
            );

        };


    window.setLocations =
        function(locations) {

            window.clearLocations();

            if (
                !Array.isArray(
                    locations
                )
            ) {

                return;

            }

            locations.forEach(
                function(location) {

                    const latitude =
                        Number(
                            location.latitude
                        );

                    const longitude =
                        Number(
                            location.longitude
                        );

                    if (
                        !Number.isFinite(
                            latitude
                        )
                        || !Number.isFinite(
                            longitude
                        )
                    ) {

                        return;

                    }

                    const locationId =
                        String(
                            location.id
                            || ""
                        );

                    const name =
                        String(
                            location.name
                            || location.value
                            || "Location"
                        );

                    const color =
                        String(
                            location.marker_color
                            || "#e072c4"
                        );

                    const marker =
                        L.marker(
                            [
                                latitude,
                                longitude
                            ],
                            {
                                icon:
                                    createMarkerIcon(
                                        color
                                    )
                            }
                        );

                    const popup =
                        '<div class="location-popup">' +

                        '<div class="location-popup-title">' +
                        escapeHtml(
                            name
                        ) +
                        '</div>' +

                        '<div class="location-popup-coordinates">' +
                        latitude.toFixed(7) +
                        ", " +
                        longitude.toFixed(7) +
                        '</div>' +

                        '</div>';

                    marker.bindPopup(
                        popup
                    );

                    marker.on(
                        "click",

                        function() {

                            if (
                                qtBridge
                                && qtBridge.on_marker_clicked
                            ) {

                                qtBridge.on_marker_clicked(
                                    locationId
                                );

                            }

                        }
                    );

                    marker.addTo(
                        markerGroup
                    );

                    markers[
                        locationId
                    ] = marker;

                }
            );

        };


    window.focusLocation =
        function(
            latitude,
            longitude,
            zoomLevel
        ) {

            const lat =
                Number(
                    latitude
                );

            const lon =
                Number(
                    longitude
                );

            const zoom =
                Number(
                    zoomLevel
                );

            if (
                !Number.isFinite(
                    lat
                )
                || !Number.isFinite(
                    lon
                )
            ) {

                return;

            }

            map.setView(
                [
                    lat,
                    lon
                ],
                Number.isFinite(
                    zoom
                )
                    ? zoom
                    : 17
            );

        };


    window.focusMarker =
        function(
            locationId,
            zoomLevel
        ) {

            const marker =
                markers[
                    String(
                        locationId
                    )
                ];

            if (
                !marker
            ) {

                return;

            }

            const latLng =
                marker.getLatLng();

            map.setView(
                latLng,
                Number(
                    zoomLevel
                ) || 17
            );

            marker.openPopup();

        };


    window.fitAllLocations =
        function() {

            const layers =
                markerGroup.getLayers();

            if (
                layers.length === 0
            ) {

                return;

            }

            if (
                layers.length === 1
            ) {

                const latLng =
                    layers[
                        0
                    ].getLatLng();

                map.setView(
                    latLng,
                    17
                );

                return;

            }

            map.fitBounds(
                markerGroup.getBounds(),
                {
                    padding: [
                        40,
                        40
                    ]
                }
            );

        };

</script>

</body>
</html>
"""

    # ==========================================================
    # Locations
    # ==========================================================

    def set_locations(
        self,
        locations: list[dict[str, Any]],
    ) -> None:
        """
        Replace currently displayed map locations.
        """

        if not isinstance(
            locations,
            list,
        ):

            locations = []

        self._locations = [
            dict(
                location
            )
            for location in locations
            if isinstance(
                location,
                dict,
            )
        ]

        location_count = len(
            self._locations
        )

        self.location_count_label.setText(
            (
                f"{location_count} location"
                if location_count == 1
                else f"{location_count} locations"
            )
        )

        if self._selected_location_id:

            selected_location = (
                self._find_location(
                    self._selected_location_id
                )
            )

            if selected_location is None:

                self._selected_location_id = None

                self._clear_location_details()

            else:

                self._display_location_details(
                    selected_location
                )

        if not self._map_ready:

            return

        self._send_locations_to_map()

    def _send_locations_to_map(
        self,
    ) -> None:

        payload = json.dumps(
            self._locations,
            ensure_ascii=False,
            default=str,
        )

        self.web_view.page().runJavaScript(
            (
                "window.setLocations("
                f"{payload}"
                ");"
            )
        )

    def _find_location(
        self,
        location_id: str,
    ) -> dict[str, Any] | None:
        """
        Find map location by entity identifier.
        """

        normalized_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_id:

            return None

        for location in self._locations:

            current_id = str(
                location.get(
                    "id"
                )
                or ""
            ).strip()

            if current_id == normalized_id:

                return location

        return None

    # ==========================================================
    # Selection
    # ==========================================================

    def _on_marker_selected(
        self,
        location_id: str,
    ) -> None:
        """
        Handle selected Leaflet marker.
        """

        normalized_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_id:

            return

        location = self._find_location(
            normalized_id
        )

        if location is None:

            return

        self._selected_location_id = (
            normalized_id
        )

        self._display_location_details(
            location
        )

        self.attach_photo_button.setEnabled(
            True
        )

        self.photos_status_label.setText(
            "Loading photos..."
        )

        self.location_photos_list.clear()

        self.location_photos_requested.emit(
            normalized_id
        )

        self.marker_selected.emit(
            normalized_id
        )


    def select_location(
        self,
        location_id: str,
        *,
        focus: bool = False,
        zoom: int = 17,
    ) -> None:
        """
        Select one location from Python side.
        """

        location = self._find_location(
            location_id
        )

        if location is None:

            return

        normalized_id = str(
            location.get(
                "id"
            )
            or ""
        ).strip()

        if not normalized_id:

            return

        self._selected_location_id = (
            normalized_id
        )

        self._display_location_details(
            location
        )

        if focus:

            self.focus_marker(
                normalized_id,
                zoom=zoom,
            )

    # ==========================================================
    # Details
    # ==========================================================

    def _display_location_details(
        self,
        location: dict[str, Any],
    ) -> None:
        """
        Display selected location information.
        """

        self.details_status_label.setText(
            "Location selected"
        )

        self.edit_location_button.setEnabled(
            True
        )

        name = str(
            location.get(
                "name"
            )
            or location.get(
                "value"
            )
            or "Location"
        ).strip()

        self.location_name_label.setText(
            name
        )

        latitude = location.get(
            "latitude"
        )

        longitude = location.get(
            "longitude"
        )

        altitude = location.get(
            "altitude"
        )

        self.latitude_value.setText(
            self._format_coordinate(
                latitude
            )
        )

        self.longitude_value.setText(
            self._format_coordinate(
                longitude
            )
        )

        self.altitude_value.setText(
            self._format_altitude(
                altitude
            )
        )

        location_id = str(
            location.get(
                "id"
            )
            or ""
        ).strip()

        self.location_id_value.setText(
            location_id
            or "—"
        )

        description = str(
            location.get(
                "description"
            )
            or ""
        ).strip()

        self.description_text.setPlainText(
            description
        )

        metadata = location.get(
            "metadata"
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

        source = metadata.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):

            source = {}

        source_type = str(
            source.get(
                "type"
            )
            or ""
        ).strip()

        source_method = str(
            source.get(
                "method"
            )
            or ""
        ).strip()

        evidence_id = str(
            source.get(
                "evidence_id"
            )
            or ""
        ).strip()

        if (
            source_type
            and source_method
        ):

            source_display = (
                f"{source_type} ({source_method})"
            )

        elif source_type:

            source_display = source_type

        elif source_method:

            source_display = source_method

        else:

            source_display = "—"

        self.source_type_value.setText(
            source_display
        )

        self.source_evidence_value.setText(
            evidence_id
            or "—"
        )

        provenance_lines: list[str] = []

        if source_type:

            provenance_lines.append(
                f"Source type: {source_type}"
            )

        if source_method:

            provenance_lines.append(
                f"Method: {source_method}"
            )

        if evidence_id:

            provenance_lines.append(
                f"Evidence ID: {evidence_id}"
            )

        if not provenance_lines:

            provenance_lines.append(
                "No provenance information."
            )

        self.provenance_text.setPlainText(
            "\n".join(
                provenance_lines
            )
        )

    def _clear_location_details(
        self,
    ) -> None:
        """
        Clear location information panel.
        """

        self.details_status_label.setText(
            "Select a marker on the map."
        )

        self.edit_location_button.setEnabled(
            False
        )

        self.edit_widget.setVisible(
            False
        )

        self._editing_location = False

        self.location_name_label.setText(
            "No location selected"
        )

        self.latitude_value.setText(
            "—"
        )

        self.longitude_value.setText(
            "—"
        )

        self.altitude_value.setText(
            "—"
        )

        self.location_id_value.setText(
            "—"
        )

        self.source_type_value.setText(
            "—"
        )

        self.source_evidence_value.setText(
            "—"
        )

        self.description_text.clear()

        self.provenance_text.clear()

        self._location_photos = []

        self._selected_photo_evidence_id = None

        self.location_photos_list.clear()

        self.photos_status_label.setText(
            "Select a location to load photos."
        )

        self.attach_photo_button.setEnabled(
            False
        )

        self.remove_photo_button.setEnabled(
            False
        )

    @staticmethod
    def _format_coordinate(
        value: Any,
    ) -> str:

        try:

            return f"{float(value):.7f}"

        except (
            TypeError,
            ValueError,
        ):

            return "—"

    @staticmethod
    def _format_altitude(
        value: Any,
    ) -> str:

        if value is None:

            return "—"

        try:

            return (
                f"{float(value):.2f} m"
            )

        except (
            TypeError,
            ValueError,
        ):

            return str(
                value
            )


    # ==========================================================
    # Location photos
    # ==========================================================

    def set_location_photos(
        self,
        location_id: str,
        photos: list[dict[str, Any]],
    ) -> None:
        """
        Display photos attached to selected LOCATION.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        if (
            not normalized_location_id
            or normalized_location_id
            != self._selected_location_id
        ):

            return

        if not isinstance(
            photos,
            list,
        ):

            photos = []

        self._location_photos = [
            dict(
                photo
            )
            for photo in photos
            if isinstance(
                photo,
                dict,
            )
        ]

        self._selected_photo_evidence_id = None

        self._render_location_photos()


    def _render_location_photos(
        self,
    ) -> None:
        """
        Render current Location photo collection.
        """

        self.location_photos_list.clear()

        self.remove_photo_button.setEnabled(
            False
        )

        if not self._location_photos:

            self.photos_status_label.setText(
                "No photos attached to this location."
            )

            return

        self.photos_status_label.setText(
            (
                f"{len(self._location_photos)} photo"
                if len(self._location_photos) == 1
                else (
                    f"{len(self._location_photos)} photos"
                )
            )
        )

        for photo in self._location_photos:

            evidence_id = str(
                photo.get(
                    "id"
                )
                or ""
            ).strip()

            title = str(
                photo.get(
                    "title"
                )
                or "Untitled image"
            ).strip()

            file_path = str(
                photo.get(
                    "file_path"
                )
                or ""
            ).strip()

            is_primary = bool(
                photo.get(
                    "is_primary",
                    False,
                )
            )

            relationship = str(
                photo.get(
                    "relationship"
                )
                or ""
            ).strip()

            if is_primary:

                relation_label = (
                    "GPS SOURCE"
                )

            elif relationship:

                relation_label = (
                    relationship.upper()
                )

            else:

                relation_label = (
                    "ATTACHED"
                )

            item = QListWidgetItem(
                (
                    f"{title}\n"
                    f"{relation_label}"
                )
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                photo,
            )

            item.setToolTip(
                (
                    f"{title}\n"
                    f"Evidence: {evidence_id}\n"
                    f"{file_path or 'File unavailable'}"
                )
            )

            if file_path:

                pixmap = QPixmap(
                    file_path
                )

                if not pixmap.isNull():

                    preview = pixmap.scaled(
                        QSize(
                            140,
                            100,
                        ),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                    item.setIcon(
                        QIcon(
                            preview
                        )
                    )

            self.location_photos_list.addItem(
                item
            )


    def _on_location_photo_selection_changed(
        self,
    ) -> None:
        """
        Update selected Evidence in the Location panel.
        """

        selected_items = (
            self.location_photos_list
            .selectedItems()
        )

        if not selected_items:

            self._selected_photo_evidence_id = None

            self.remove_photo_button.setEnabled(
                False
            )

            return

        photo = selected_items[
            0
        ].data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            photo,
            dict,
        ):

            self._selected_photo_evidence_id = None

            self.remove_photo_button.setEnabled(
                False
            )

            return

        evidence_id = str(
            photo.get(
                "id"
            )
            or ""
        ).strip()

        self._selected_photo_evidence_id = (
            evidence_id
            or None
        )

        is_primary = bool(
            photo.get(
                "is_primary",
                False,
            )
        )

        self.remove_photo_button.setEnabled(
            bool(
                evidence_id
            )
            and not is_primary
        )


    def _request_attach_location_photo(
        self,
    ) -> None:
        """
        Request attaching an existing image Evidence.
        """

        location_id = str(
            self._selected_location_id
            or ""
        ).strip()

        if not location_id:

            return

        self.attach_location_photo_requested.emit(
            location_id
        )


    def _request_detach_location_photo(
        self,
    ) -> None:
        """
        Request removal of selected attached photo.
        """

        location_id = str(
            self._selected_location_id
            or ""
        ).strip()

        evidence_id = str(
            self._selected_photo_evidence_id
            or ""
        ).strip()

        if (
            not location_id
            or not evidence_id
        ):

            return

        self.detach_location_photo_requested.emit(
            location_id,
            evidence_id,
        )


    def _open_location_photo(
        self,
        item: QListWidgetItem,
    ) -> None:
        """
        Request opening selected Evidence in Photo Workspace.
        """

        photo = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            photo,
            dict,
        ):

            return

        evidence_id = str(
            photo.get(
                "id"
            )
            or ""
        ).strip()

        if not evidence_id:

            return

        self.open_location_photo_requested.emit(
            evidence_id
        )

    # ==========================================================
    # Layer
    # ==========================================================

    def _on_layer_changed(
        self,
    ) -> None:

        layer_name = (
            self.layer_combo.currentData()
        )

        if not layer_name:

            return

        self.web_view.page().runJavaScript(
            (
                "window.setMapLayer("
                f"{json.dumps(str(layer_name))}"
                ");"
            )
        )

    # ==========================================================
    # Focus
    # ==========================================================

    def focus_location(
        self,
        latitude: float,
        longitude: float,
        *,
        zoom: int = 17,
    ) -> None:

        try:

            normalized_latitude = float(
                latitude
            )

            normalized_longitude = float(
                longitude
            )

            normalized_zoom = int(
                zoom
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        if not self._map_ready:

            self._pending_focus = (
                normalized_latitude,
                normalized_longitude,
                normalized_zoom,
            )

            return

        self.web_view.page().runJavaScript(
            (
                "window.focusLocation("
                f"{normalized_latitude},"
                f"{normalized_longitude},"
                f"{normalized_zoom}"
                ");"
            )
        )

    def focus_marker(
        self,
        location_id: str,
        *,
        zoom: int = 17,
    ) -> None:

        normalized_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_id:

            return

        self.web_view.page().runJavaScript(
            (
                "window.focusMarker("
                f"{json.dumps(normalized_id)},"
                f"{int(zoom)}"
                ");"
            )
        )

    def fit_locations(
        self,
    ) -> None:

        if not self._map_ready:

            return

        self.web_view.page().runJavaScript(
            "window.fitAllLocations();"
        )

    # ==========================================================
    # Map lifecycle
    # ==========================================================

    def _on_map_ready(
        self,
    ) -> None:

        self._map_ready = True

        self._send_locations_to_map()

        self._on_layer_changed()

        if (
            self._pending_focus
            is not None
        ):

            (
                latitude,
                longitude,
                zoom,
            ) = self._pending_focus

            self._pending_focus = None

            self.focus_location(
                latitude,
                longitude,
                zoom=zoom,
            )

    # ==========================================================
    # Reload
    # ==========================================================

    def reload_map(
        self,
    ) -> None:

        self._map_ready = False

        self._load_map()

    def _start_location_edit(
        self,
    ) -> None:
        """
        Enter location edit mode.
        """

        if not self._selected_location_id:

            return

        location = self._find_location(
            self._selected_location_id
        )

        if location is None:

            return

        self._editing_location = True

        name = str(
            location.get(
                "name"
            )
            or location.get(
                "value"
            )
            or ""
        ).strip()

        description = str(
            location.get(
                "description"
            )
            or ""
        )

        marker_color = str(
            location.get(
                "marker_color"
            )
            or "#e072c4"
        ).strip()

        self._selected_marker_color = (
            marker_color
        )

        self.edit_name_input.setText(
            name
        )

        self.edit_description_input.setPlainText(
            description
        )

        self.edit_color_value.setText(
            marker_color
        )

        self.edit_widget.setVisible(
            True
        )

        self.edit_location_button.setVisible(
            False
        )


    def _cancel_location_edit(
        self,
    ) -> None:
        """
        Leave location edit mode.
        """

        self._editing_location = False

        self.edit_widget.setVisible(
            False
        )

        self.edit_location_button.setVisible(
            True
        )


    def _choose_marker_color(
        self,
    ) -> None:
        """
        Select marker color.
        """

        initial_color = QColor(
            self._selected_marker_color
        )

        color = QColorDialog.getColor(
            initial_color,
            self,
            "Select marker color",
        )

        if not color.isValid():

            return

        self._selected_marker_color = (
            color.name()
        )

        self.edit_color_value.setText(
            self._selected_marker_color
        )


    def _save_location_edit(
        self,
    ) -> None:
        """
        Emit requested location changes.
        """

        location_id = str(
            self._selected_location_id
            or ""
        ).strip()

        if not location_id:

            return

        marker_name = (
            self.edit_name_input
            .text()
            .strip()
        )

        description = (
            self.edit_description_input
            .toPlainText()
            .strip()
        )

        marker_color = str(
            self._selected_marker_color
            or "#e072c4"
        ).strip()

        self.location_edit_requested.emit(
            location_id,
            marker_name,
            description,
            marker_color,
        )