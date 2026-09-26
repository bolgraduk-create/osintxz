from pathlib import Path


MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
BROWSER_QML = Path("app/interface/desktop/qml/components/MapSourceBrowserDialog.qml")
MAP_HTML = Path("app/interface/desktop/qml/map/map_engine.html")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_ui3_removes_duplicate_legacy_map_control_rows():
    qml = _read(MAP_QML)

    assert 'text: "LAYERS"' not in qml
    assert 'text: "BASE MAP"' not in qml
    assert qml.count("MapSourceToolbar {") == 1


def test_geo_ui3_toolbar_is_single_clear_map_compare_control():
    qml = _read(TOOLBAR_QML)

    assert 'text: "Browse"' in qml
    assert 'text: "Layers"' in qml
    assert 'text: "Tools"' in qml
    assert 'text: root.compareEnabled ? "Exit compare" : "Compare"' in qml
    assert 'text: "Compare with"' in qml
    assert 'text: "Opacity"' in qml

    assert "CheckBox {" not in qml
    assert 'text: "+ Source"' not in qml
    assert 'text: "Remove"' not in qml


def test_geo_ui3_unavailable_sentinel_is_filtered_from_primary_selector():
    qml = _read(TOOLBAR_QML)

    assert "property bool satelliteAvailable: false" in qml
    assert 'String((source || {}).id || "") === "sentinel_selected"' in qml
    assert "return root.satelliteAvailable" in qml
    assert "if (!root.sourceAvailable(source))" in qml


def test_geo_ui3_custom_source_management_lives_in_browser():
    qml = _read(BROWSER_QML)

    assert 'text: "+ Add source"' in qml
    assert "signal removeSourceRequested(string sourceId)" in qml
    assert 'text: "Remove"' in qml
    assert "visible: Boolean(sourceRow.modelData.userDefined)" in qml


def test_geo_ui3_map_panel_names_active_source_and_inspector_is_contextual():
    qml = _read(MAP_QML)

    assert 'property bool toolsOpen: false' in qml
    assert 'visible: root.toolsOpen' in qml
    assert 'title: "GEO Tools"' in qml
    assert 'text: "No map point selected"' in qml
    assert 'text: "EXPLORE COORDINATES"' in qml
    assert 'text: geoBridge.busy ? "Exploring…" : "Explore area"' in qml

    assert 'visible: String(root.selectedMarker.previewUrl || "").length > 0' in qml
    assert 'headerHeight: 46' in qml
    assert 'subtitle: ""' in qml


def test_geo_ui3_osm_dark_treatment_preserves_readability():
    html = _read(MAP_HTML)

    assert ".tile.dark-filter{filter:saturate(68%) brightness(62%) contrast(108%)}" in html
    assert "invert(92%)" not in html
    assert "background:rgba(4,19,29,.08)" in html
