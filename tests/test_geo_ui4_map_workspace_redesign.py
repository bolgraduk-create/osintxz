from pathlib import Path


MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
BROWSER_QML = Path("app/interface/desktop/qml/components/MapSourceBrowserDialog.qml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_ui4_map_workspace_is_map_first():
    qml = _read(MAP_QML)

    assert "property bool toolsOpen: false" in qml
    assert "onToolsRequested: root.toolsOpen = !root.toolsOpen" in qml
    assert "visible: root.toolsOpen" in qml
    assert "Layout.preferredWidth: visible ? 318 : 0" in qml
    assert "headerHeight: 46" in qml
    assert 'subtitle: ""' in qml
    assert "Layout.preferredHeight: 38" in qml


def test_geo_ui4_toolbar_is_compact_and_progressive():
    qml = _read(TOOLBAR_QML)

    assert "implicitHeight: root.compareEnabled ? 94 : 52" in qml
    assert 'text: "Browse"' in qml
    assert 'text: "Layers"' in qml
    assert 'text: "Tools"' in qml
    assert 'text: "Compare with"' in qml
    assert '{ key: "side_by_side", label: "Split" }' in qml
    assert 'visible: root.compareMode === "overlay"' in qml


def test_geo_ui4_source_browser_has_simple_category_filter():
    qml = _read(BROWSER_QML)

    assert 'property string categoryFilter: "all"' in qml
    assert '{ key: "all", label: "All maps" }' in qml
    assert '{ key: "satellite", label: "Satellite" }' in qml
    assert '{ key: "historical", label: "Historical" }' in qml
    assert '{ key: "terrain", label: "Terrain" }' in qml
    assert "categoryMatches" in qml
    assert 'description: "Choose a basemap or comparison layer."' in qml


MAP_HTML = Path("app/interface/desktop/qml/map/map_engine.html")
MAP_SOURCES = Path("app/geo_intelligence/map_sources.py")


def test_geo_ui4_map_canvas_uses_contextual_chrome_and_source_fit():
    html = _read(MAP_HTML)
    sources = _read(MAP_SOURCES)

    assert '#status{position:absolute;left:12px;bottom:10px;z-index:20;display:none' in html
    assert '#legend{position:absolute;left:12px;bottom:12px;z-index:20;display:none' in html
    assert "function showStatus(message)" in html
    assert 'primaryLabelEl.style.display="none"' in html
    assert 'primaryLabelEl.style.display="block"' in html
    assert 'legendEl.style.display=markers.length ? "flex" : "none"' in html
    assert "const primaryChanged=nextPrimaryKey!==lastPrimarySourceKey" in html
    assert "Array.isArray(primarySource.metadata.viewBbox)" in html
    assert "fitBounds(sourceViewBbox)" in html

    assert '"viewBbox": [14.1, 49.0, 24.2, 54.9]' in sources
    assert '"viewBbox": [5.5, 47.2, 15.5, 55.1]' in sources
    assert '"viewBbox": [-5.5, 41.0, 9.8, 51.5]' in sources
    assert '"viewBbox": [-8.7, 49.8, 2.1, 60.9]' in sources
