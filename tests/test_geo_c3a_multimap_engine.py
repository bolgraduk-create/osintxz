from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.geo_intelligence.map_sources import (
    BUILTIN_MAP_SOURCES,
    MapSourceDescriptor,
    MapSourceRegistry,
)


MAP_SOURCES = Path("app/geo_intelligence/map_sources.py")
GEO_BRIDGE = Path("app/interface/desktop/bridges/geo_bridge.py")
MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
DIALOG_QML = Path("app/interface/desktop/qml/components/AddMapSourceDialog.qml")
WEB_QML = Path("app/interface/desktop/qml/components/InteractiveMapView.qml")
MAP_HTML = Path("app/interface/desktop/qml/map/map_engine.html")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_c3a_python_modules_remain_syntactically_valid():
    ast.parse(_read(MAP_SOURCES))
    ast.parse(_read(GEO_BRIDGE))


def test_geo_c3a_builtin_sources_cover_streets_schematic_and_dynamic_satellite():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert set(sources) >= {
        "osm_standard",
        "local_schematic",
        "sentinel_selected",
    }

    osm = sources["osm_standard"]
    assert osm.kind == "xyz"
    assert osm.url == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert osm.attribution == "© OpenStreetMap contributors"
    assert osm.metadata["darkFilter"] is True
    assert osm.metadata["prefetchAllowed"] is False

    schematic = sources["local_schematic"]
    assert schematic.kind == "schematic"
    assert schematic.compare_supported is False

    sentinel = sources["sentinel_selected"]
    assert sentinel.kind == "satellite_dynamic"
    assert sentinel.metadata["requiresScene"] is True


def test_geo_c3a_xyz_source_requires_tile_placeholders():
    with pytest.raises(ValueError):
        MapSourceDescriptor(
            id="bad_xyz",
            name="Bad XYZ",
            kind="xyz",
            url="https://example.org/tiles.png",
        )

    source = MapSourceDescriptor(
        id="valid_xyz",
        name="Valid XYZ",
        kind="xyz",
        url="https://example.org/{z}/{x}/{y}.png",
    )
    assert source.kind == "xyz"


def test_geo_c3a_custom_source_url_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        MapSourceDescriptor(
            id="credentialed",
            name="Credentialed",
            kind="xyz",
            url="https://user:secret@example.org/{z}/{x}/{y}.png",
        )


def test_geo_c3a_registry_persists_custom_xyz_source(tmp_path):
    storage = tmp_path / "map_sources.json"
    registry = MapSourceRegistry(storage_path=storage)

    source = registry.add_custom(
        name="My Tiles",
        kind="xyz",
        url="https://maps.example.org/{z}/{x}/{y}.png",
        attribution="Example Maps",
        terms_url="https://maps.example.org/terms",
        min_zoom=2,
        max_zoom=17,
    )

    assert source.user_defined is True
    assert source.id.startswith("custom_my_tiles")
    assert storage.is_file()

    restored = MapSourceRegistry(storage_path=storage)
    loaded = restored.get(source.id)

    assert loaded is not None
    assert loaded.name == "My Tiles"
    assert loaded.kind == "xyz"
    assert loaded.url == "https://maps.example.org/{z}/{x}/{y}.png"
    assert loaded.attribution == "Example Maps"
    assert loaded.min_zoom == 2
    assert loaded.max_zoom == 17

    assert restored.remove_custom(source.id) is True
    assert MapSourceRegistry(storage_path=storage).get(source.id) is None


def test_geo_c3a_registry_persists_custom_wms_source(tmp_path):
    registry = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )

    source = registry.add_custom(
        name="Analyst WMS",
        kind="wms",
        url="https://geo.example.org/wms",
        attribution="Example GIS",
        wms_layers="roads,buildings",
        wms_styles="",
        wms_version="1.3.0",
        wms_transparent=True,
    )

    payload = source.to_payload()
    assert payload["kind"] == "wms"
    assert payload["wmsLayers"] == "roads,buildings"
    assert payload["wmsVersion"] == "1.3.0"
    assert payload["wmsTransparent"] is True


def test_geo_c3a_builtin_sources_cannot_be_removed(tmp_path):
    registry = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )

    assert registry.remove_custom("osm_standard") is False
    assert registry.get("osm_standard") is not None


def test_geo_c3a_bridge_exposes_map_source_registry_without_database_writes():
    bridge = _read(GEO_BRIDGE)
    sources = _read(MAP_SOURCES)

    assert "MapSourceRegistry" in bridge
    assert "def mapSources(self)" in bridge
    assert "def mapSourceMessage(self)" in bridge
    assert "def addMapSource(" in bridge
    assert "def removeMapSource(" in bridge
    assert "self._map_source_registry.add_custom(" in bridge
    assert "self._map_source_registry.remove_custom(" in bridge

    for forbidden in (
        "create_entity(",
        "create_evidence(",
        "session.commit(",
        "db.commit(",
    ):
        assert forbidden not in sources


def test_geo_c3a_toolbar_exposes_primary_secondary_and_compare_modes():
    qml = _read(TOOLBAR_QML)

    for expected in (
        'text: "MAP SOURCE"',
        'text: "Compare"',
        'text: "SECONDARY"',
        '{ key: "overlay", label: "Overlay" }',
        '{ key: "side_by_side", label: "Side by side" }',
        '{ key: "swipe", label: "Swipe" }',
        'text: "+ Source"',
        'text: "Remove"',
        'text: "Opacity"',
    ):
        assert expected in qml

    assert "signal primarySourceRequested(string sourceId)" in qml
    assert "signal secondarySourceRequested(string sourceId)" in qml
    assert "signal compareModeRequested(string mode)" in qml
    assert "signal secondaryOpacityRequested(real opacity)" in qml


def test_geo_c3a_custom_source_dialog_supports_xyz_wms_and_wmts():
    qml = _read(DIALOG_QML)

    assert 'title: "Add Map Source"' in qml
    assert 'model: ["XYZ", "WMS", "WMTS"]' in qml
    assert 'placeholderText: "WMS layer(s), comma separated"' in qml
    assert 'model: ["1.3.0", "1.1.1"]' in qml
    assert '"{z}/{x}/{y}"' not in qml
    assert "{z}" in qml
    assert "{x}" in qml
    assert "{y}" in qml
    assert "sourceSubmitted({" in qml


def test_geo_c3a_map_workspace_wires_registry_state_into_one_interactive_map():
    qml = _read(MAP_QML)
    web_qml = _read(WEB_QML)

    for expected in (
        "geoBridge.mapSources",
        'property string primaryMapSourceId:',
        'property string secondaryMapSourceId:',
        'property string compareMode: "overlay"',
        "function mapStatePayload()",
        "function materializeMapSource(sourceId)",
        "MapSourceToolbar {",
        "AddMapSourceDialog {",
        "geoBridge.addMapSource(payload)",
        "geoBridge.removeMapSource(wanted)",
        "item.mapState = Qt.binding",
        "function onComparePositionRequested(position)",
    ):
        assert expected in qml

    assert "property var mapState: ({})" in web_qml
    assert "mapState: root.mapState || ({})" in web_qml
    assert "signal comparePositionRequested(real position)" in web_qml
    assert 'target.indexOf("osintxz://compare?") === 0' in web_qml


def test_geo_c3a_engine_supports_xyz_wms_image_and_compare_in_one_viewport():
    html = _read(MAP_HTML)

    assert html.count('id="map"') == 1
    assert 'id="primaryLayer"' in html
    assert 'id="secondaryLayer"' in html
    assert 'id="compareDivider"' in html

    for expected in (
        "function xyzTileUrl(source,z,x,y)",
        "function wmsTileUrl(source,z,x,y)",
        "function renderTileLayer(state,source)",
        "function renderImageLayer(state,source)",
        "function renderRasterLayer(state,source)",
        'if(kind==="xyz" || kind==="wms" || kind==="wmts")',
        'kind==="satellite_dynamic" || kind==="image"',
        'p.set("request","GetMap")',
        'p.set("width",String(TILE_SIZE))',
        'p.set("height",String(TILE_SIZE))',
        'p.set("crs","EPSG:3857")',
        'compareMode==="overlay"',
        'compareMode==="side_by_side"',
        'compareMode!=="swipe"',
        'secondaryEl.style.clipPath="inset(0 0 0 "+leftPct+"%)"',
        "notifyComparePosition()",
    ):
        assert expected in html


def test_geo_c3a_engine_does_not_add_prefetch_or_external_js_framework():
    html = _read(MAP_HTML)

    assert "prefetch" not in html.lower()
    assert "<script src=" not in html
    assert "leaflet" not in html.lower()
    assert "maplibre" not in html.lower()
    assert "unpkg.com" not in html.lower()


def test_geo_c3a_attribution_is_source_driven_and_escaped():
    html = _read(MAP_HTML)

    assert "function escapeHtml(value)" in html
    assert "function buildAttributionEntry(source)" in html
    assert "source.attribution" in html
    assert "source.termsUrl" in html
    assert 'window.location.href="osintxz://select?' in html
    assert "osintxz://external?url=" in html


def test_geo_c3a_hybrid_is_a_multimap_preset_not_a_separate_renderer():
    qml = _read(MAP_QML)

    assert 'if (requested === "hybrid")' in qml
    assert 'root.primaryMapSourceId = "sentinel_selected"' in qml
    assert 'root.secondaryMapSourceId = "osm_standard"' in qml
    assert 'root.compareMode = "overlay"' in qml
    assert "root.secondaryOpacity = 0.42" in qml
    assert 'root.baseMapMode = "hybrid"' in qml
