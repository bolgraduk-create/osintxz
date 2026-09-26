from __future__ import annotations

import ast
from pathlib import Path


MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")
WEB_QML = Path("app/interface/desktop/qml/components/InteractiveMapView.qml")
MAP_HTML = Path("app/interface/desktop/qml/map/map_engine.html")
DESKTOP_APP = Path("app/interface/desktop/desktop_app.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_ui2_desktop_initializes_webengine_before_qapplication():
    source = _read(DESKTOP_APP)
    ast.parse(source)

    assert "from PySide6.QtWebEngineQuick import QtWebEngineQuick" in source
    assert "except ImportError:" in source
    assert "self.map_web_engine_available = QtWebEngineQuick is not None" in source
    assert "QtWebEngineQuick.initialize()" in source
    assert '"mapWebEngineAvailable"' in source

    assert source.index("QtWebEngineQuick.initialize()") < source.index(
        "self.app = QApplication("
    )


def test_geo_ui2_map_workspace_defaults_to_streets_with_schematic_fallback():
    qml = _read(MAP_QML)

    assert "property bool webEngineRuntimeAvailable" in qml
    assert 'property string baseMapMode: webEngineRuntimeAvailable ? "streets" : "schematic"' in qml
    assert 'baseMapMode === "streets"' in qml
    assert 'baseMapMode === "satellite"' in qml
    assert 'text: "Streets"' in qml
    assert 'text: "Schematic"' in qml
    assert 'text: "Satellite"' in qml
    assert 'source: active ? "../components/InteractiveMapView.qml" : ""' in qml
    assert 'root.baseMapMode = "schematic"' in qml
    assert "Interactive basemap unavailable · schematic fallback" in qml


def test_geo_ui2_keeps_existing_schematic_as_offline_safe_fallback():
    qml = _read(MAP_QML)

    assert "id: schematicMap" in qml
    assert "visible: !root.useInteractiveMap" in qml
    assert "id: projection" in qml
    assert 'source: "../../assets/images/world_map_dots.svg"' in qml
    assert "model: root.visibleMarkers()" in qml


def test_geo_ui2_interactive_map_syncs_markers_and_inspector_selection():
    qml = _read(MAP_QML)
    web_qml = _read(WEB_QML)

    assert "function selectMarkerByKey(kind, markerId)" in qml
    assert "function onMarkerSelected(kind, markerId)" in qml
    assert "root.selectMarkerByKey(kind, markerId)" in qml
    assert "interactiveMapLoader.item.focusMarker(" in qml

    assert "signal markerSelected(string kind, string markerId)" in web_qml
    assert "function syncState()" in web_qml
    assert "window.osintxzMap.setState(" in web_qml
    assert "window.osintxzMap.focusMarker(" in web_qml
    assert 'target.indexOf("osintxz://select?") === 0' in web_qml
    assert 'failedUrl.indexOf("osintxz://") !== 0' in web_qml


def test_geo_ui2_web_profile_identifies_app_and_uses_disk_cache():
    qml = _read(WEB_QML)

    assert 'storageName: "osintxz-map"' in qml
    assert "offTheRecord: false" in qml
    assert "httpCacheType: WebEngineProfile.DiskHttpCache" in qml
    assert "httpCacheMaximumSize: 268435456" in qml
    assert 'httpUserAgent: "OSINTXZ/0.1 InteractiveMap"' in qml
    assert "localContentCanAccessRemoteUrls: true" in qml
    assert "javascriptCanOpenWindows: false" in qml
    assert "webRTCPublicInterfacesOnly: true" in qml
    assert "AllowUnknownUrlSchemesFromUserInteraction" in qml


def test_geo_ui2_map_engine_is_local_and_only_fetches_visible_osm_tiles():
    html = _read(MAP_HTML)

    assert 'url:"https://tile.openstreetmap.org/{z}/{x}/{y}.png"' in html
    assert "function renderTileLayer(state,source)" in html
    assert "const minX=Math.floor(origin.x/TILE_SIZE);" in html
    assert "const maxX=Math.floor((origin.x+mapEl.clientWidth)/TILE_SIZE);" in html
    assert "const minY=Math.floor(origin.y/TILE_SIZE);" in html
    assert "const maxY=Math.floor((origin.y+mapEl.clientHeight)/TILE_SIZE);" in html
    assert "prefetch" not in html.lower()
    assert "<script src=" not in html
    assert "unpkg.com" not in html
    assert "maplibre" not in html.lower()
    assert "leaflet" not in html.lower()


def test_geo_ui2_map_engine_supports_pan_zoom_fit_and_clusters():
    html = _read(MAP_HTML)

    for expected in (
        'mapEl.addEventListener("pointerdown"',
        'mapEl.addEventListener("pointermove"',
        'mapEl.addEventListener("wheel"',
        'mapEl.addEventListener("dblclick"',
        "function fitMarkers()",
        "function clusterRows(rows)",
        'document.getElementById("zoomIn")',
        'document.getElementById("zoomOut")',
        'document.getElementById("fitBtn")',
    ):
        assert expected in html


def test_geo_ui2_dark_theme_preserves_osintxz_marker_semantics():
    html = _read(MAP_HTML)

    assert "invert(92%) hue-rotate(180deg)" in html
    assert ".kind-location{background:#c78cf4}" in html
    assert ".kind-photo{background:#e5a84b}" in html
    assert ".kind-poi{background:#49c5d8}" in html
    assert ".kind-query{background:#36cfa1}" in html
    assert "Location</span>" in html
    assert "Photo GPS</span>" in html
    assert "Live POI</span>" in html


def test_geo_ui2_osm_attribution_is_visible_and_delegates_external_opening():
    html = _read(MAP_HTML)
    qml = _read(WEB_QML)

    assert "© OpenStreetMap contributors" in html
    assert "https%3A%2F%2Fwww.openstreetmap.org%2Fcopyright" in html
    assert 'target.indexOf("osintxz://external?") === 0' in qml
    assert "desktopBridge.openExternalUrl(" in qml


def test_geo_ui2_satellite_mode_extends_interactive_map_without_removing_fallback():
    qml = _read(MAP_QML)
    web_qml = _read(WEB_QML)
    html = _read(MAP_HTML)

    assert 'text: "Satellite"' in qml
    assert "root.selectedSatelliteScene.renderUrl" in qml
    assert "root.selectedSatelliteScene.quicklookUrl" in qml
    assert "item.satelliteScene = Qt.binding" in qml
    assert "property var satelliteScene" in web_qml
    assert "satelliteScene: root.satelliteScene" in web_qml
    assert "function renderSatellite()" in html
    assert "function fitSatellite()" in html
    assert "function renderImageLayer(state,source)" in html
    assert 'kind:"satellite_dynamic"' in html
    assert "legacySatelliteSource(scene)" in html
    assert "satelliteDisplayUrl(scene)" in html
