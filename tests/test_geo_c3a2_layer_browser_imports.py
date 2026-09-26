from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.geo_intelligence.map_layers import (
    MapLayerRegistry,
)
from app.geo_intelligence.map_sources import (
    MapSourceRegistry,
)


MAP_LAYERS = Path("app/geo_intelligence/map_layers.py")
MAP_SOURCES = Path("app/geo_intelligence/map_sources.py")
GEO_BRIDGE = Path("app/interface/desktop/bridges/geo_bridge.py")
MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
BROWSER_QML = Path("app/interface/desktop/qml/components/MapSourceBrowserDialog.qml")
LAYERS_QML = Path("app/interface/desktop/qml/components/MapLayersDialog.qml")
ADD_SOURCE_QML = Path("app/interface/desktop/qml/components/AddMapSourceDialog.qml")
WEB_QML = Path("app/interface/desktop/qml/components/InteractiveMapView.qml")
MAP_HTML = Path("app/interface/desktop/qml/map/map_engine.html")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_c3a2_python_modules_are_syntactically_valid():
    ast.parse(_read(MAP_LAYERS))
    ast.parse(_read(MAP_SOURCES))
    ast.parse(_read(GEO_BRIDGE))


def test_geo_c3a2_geojson_import_normalizes_supported_geometry(tmp_path):
    source = tmp_path / "sample.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Point A"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [30.7, 46.4],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Route"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [30.7, 46.4],
                                [30.8, 46.5],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Area"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [30.6, 46.3],
                                [30.9, 46.3],
                                [30.9, 46.6],
                                [30.6, 46.3],
                            ]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    registry = MapLayerRegistry(storage_dir=tmp_path / "layers")
    layer = registry.import_file(source)

    assert layer.source_format == "geojson"
    assert len(layer.features) == 3
    assert [row["geometryType"] for row in layer.features] == [
        "Point",
        "LineString",
        "Polygon",
    ]
    assert layer.features[0]["title"] == "Point A"
    assert layer.bounds == [30.6, 46.3, 30.9, 46.6]


def test_geo_c3a2_kml_import_parses_points_lines_and_polygons(tmp_path):
    source = tmp_path / "sample.kml"
    source.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Camera</name>
      <Point><coordinates>30.72,46.48,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Path</name>
      <LineString>
        <coordinates>30.70,46.47 30.74,46.49</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Zone</name>
      <Polygon>
        <outerBoundaryIs><LinearRing>
          <coordinates>
            30.70,46.47 30.75,46.47 30.75,46.50 30.70,46.47
          </coordinates>
        </LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>""",
        encoding="utf-8",
    )

    registry = MapLayerRegistry(storage_dir=tmp_path / "layers")
    layer = registry.import_file(source)

    assert layer.source_format == "kml"
    assert [row["geometryType"] for row in layer.features] == [
        "Point",
        "LineString",
        "Polygon",
    ]
    assert layer.features[0]["title"] == "Camera"


def test_geo_c3a2_gpx_import_parses_waypoint_route_and_track(tmp_path):
    source = tmp_path / "route.gpx"
    source.write_text(
        """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="46.48" lon="30.72"><name>Start</name></wpt>
  <rte>
    <name>Route A</name>
    <rtept lat="46.48" lon="30.72"/>
    <rtept lat="46.49" lon="30.73"/>
  </rte>
  <trk>
    <name>Track A</name>
    <trkseg>
      <trkpt lat="46.49" lon="30.73"/>
      <trkpt lat="46.50" lon="30.75"/>
    </trkseg>
  </trk>
</gpx>""",
        encoding="utf-8",
    )

    registry = MapLayerRegistry(storage_dir=tmp_path / "layers")
    layer = registry.import_file(source)

    assert layer.source_format == "gpx"
    assert len(layer.features) == 3
    assert layer.features[0]["geometryType"] == "Point"
    assert layer.features[1]["title"] == "Route A"
    assert layer.features[2]["title"] == "Track A"


def test_geo_c3a2_xml_import_blocks_doctype_and_entities(tmp_path):
    source = tmp_path / "unsafe.kml"
    source.write_text(
        """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<kml><Placemark><name>&xxe;</name></Placemark></kml>""",
        encoding="utf-8",
    )

    registry = MapLayerRegistry(storage_dir=tmp_path / "layers")

    with pytest.raises(ValueError, match="DOCTYPE or ENTITY"):
        registry.import_file(source)


def test_geo_c3a2_vector_layer_state_persists_without_original_file(tmp_path):
    source = tmp_path / "points.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"name": "A"},
                "geometry": {
                    "type": "Point",
                    "coordinates": [30.7, 46.4],
                },
            }
        ),
        encoding="utf-8",
    )
    storage = tmp_path / "layers"
    registry = MapLayerRegistry(storage_dir=storage)
    layer = registry.import_file(
        source,
        scope_id="case-123",
    )

    assert layer.scope_id == "case-123"
    assert registry.set_visibility(layer.id, False) is True
    assert registry.set_opacity(layer.id, 0.35) is True

    source.unlink()

    restored = MapLayerRegistry(storage_dir=storage)
    loaded = restored.get(layer.id)

    assert loaded is not None
    assert loaded.scope_id == "case-123"
    assert loaded.visible is False
    assert loaded.opacity == pytest.approx(0.35)
    assert len(loaded.features) == 1

    assert restored.remove(layer.id) is True
    assert MapLayerRegistry(storage_dir=storage).get(layer.id) is None


def test_geo_c3a2_wmts_source_persists_required_parameters(tmp_path):
    registry = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )

    source = registry.add_custom(
        name="Analyst WMTS",
        kind="wmts",
        url="https://geo.example.org/wmts",
        attribution="Example WMTS",
        wmts_layer="imagery",
        wmts_style="default",
        wmts_format="image/png",
        wmts_matrix_set="EPSG:3857",
        wmts_matrix_prefix="EPSG:3857:",
    )

    payload = source.to_payload()

    assert payload["kind"] == "wmts"
    assert payload["wmtsLayer"] == "imagery"
    assert payload["wmtsMatrixSet"] == "EPSG:3857"
    assert payload["wmtsMatrixPrefix"] == "EPSG:3857:"

    restored = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )
    loaded = restored.get(source.id)

    assert loaded is not None
    assert loaded.kind == "wmts"
    assert loaded.wmts_layer == "imagery"
    assert loaded.wmts_matrix_set == "EPSG:3857"


def test_geo_c3a2_wmts_requires_layer_and_matrix_set(tmp_path):
    registry = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )

    with pytest.raises(ValueError, match="layer name"):
        registry.add_custom(
            name="Bad WMTS",
            kind="wmts",
            url="https://geo.example.org/wmts",
            wmts_matrix_set="EPSG:3857",
        )

    with pytest.raises(ValueError, match="tile matrix set"):
        registry.add_custom(
            name="Bad WMTS",
            kind="wmts",
            url="https://geo.example.org/wmts",
            wmts_layer="imagery",
        )


def test_geo_c3a2_bridge_exposes_layer_import_and_controls():
    bridge = _read(GEO_BRIDGE)

    for expected in (
        "MapLayerRegistry",
        "def mapLayers(self)",
        "def mapLayerMessage(self)",
        "def importMapLayer(",
        "def setMapLayerVisibility(",
        "def setMapLayerOpacity(",
        "def removeMapLayer(",
        "QUrl(normalized)",
        "qurl.toLocalFile()",
    ):
        assert expected in bridge


def test_geo_c3a2_source_browser_is_searchable_and_can_compare():
    qml = _read(BROWSER_QML)

    assert 'title: "Map Source Browser"' in qml
    assert "function filteredSources()" in qml
    assert 'placeholderText: "Search maps by name, type, category..."' in qml
    assert "signal sourceChosen(string sourceId, bool asSecondary)" in qml
    assert 'text: "Compare"' in qml
    assert 'text: "+ Add source"' in qml
    assert '"XYZ · WMS · WMTS · Sentinel"' in qml


def test_geo_c3a2_layers_dialog_controls_investigation_and_imported_layers():
    qml = _read(LAYERS_QML)

    for expected in (
        'title: "Map Layers"',
        'text: "INVESTIGATION"',
        'text: "Locations"',
        'text: "Photo GPS"',
        'text: "Nearby POI"',
        'text: "IMPORTED"',
        '"GeoJSON · KML · GPX"',
        'text: "Import layer"',
        "signal layerVisibilityRequested(string layerId, bool visible)",
        "signal layerOpacityRequested(string layerId, real opacity)",
        "signal fitLayerRequested(string layerId)",
        "signal removeLayerRequested(string layerId)",
    ):
        assert expected in qml


def test_geo_c3a2_add_source_dialog_supports_wmts_fields():
    qml = _read(ADD_SOURCE_QML)

    assert 'model: ["XYZ", "WMS", "WMTS"]' in qml
    assert 'placeholderText: "WMTS layer"' in qml
    assert 'placeholderText: "Tile matrix set"' in qml
    assert "wmtsMatrixPrefix" in qml
    assert 'kind: sourceType.currentIndex === 1' in qml


def test_geo_c3a2_map_workspace_wires_file_dialog_browser_and_layers():
    qml = _read(MAP_QML)

    for expected in (
        "import QtQuick.Dialogs",
        "geoBridge.mapLayers",
        "function scopedMapLayers()",
        "layer.scopeId",
        "vectorLayers: root.mapLayers",
        "MapSourceBrowserDialog {",
        "MapLayersDialog {",
        "FileDialog {",
        'title: "Import geographic layer"',
        '"Geographic layers (*.geojson *.json *.kml *.gpx)"',
        "geoBridge.importMapLayer(",
        "String(desktopBridge.currentCaseId || \"global\")",
        "geoBridge.setMapLayerVisibility(layerId, visible)",
        "geoBridge.setMapLayerOpacity(layerId, opacity)",
        "geoBridge.removeMapLayer(layerId)",
        "function fitMapLayer(layerId)",
        "interactiveMapLoader.item.fitBounds(bounds)",
    ):
        assert expected in qml


def test_geo_c3a2_web_wrapper_exposes_fit_bounds():
    qml = _read(WEB_QML)

    assert "function fitBounds(bounds)" in qml
    assert "window.osintxzMap.fitBounds(" in qml


def test_geo_c3a2_engine_renders_wmts_and_vector_layers():
    html = _read(MAP_HTML)

    for expected in (
        "function wmtsTileUrl(source,z,x,y)",
        'p.set("SERVICE","WMTS")',
        'p.set("REQUEST","GetTile")',
        'p.set("TILEMATRIXSET",String(source.wmtsMatrixSet || ""))',
        'p.set("TILEROW",String(y))',
        'p.set("TILECOL",String(x))',
        'if(kind==="xyz" || kind==="wms" || kind==="wmts")',
        'id="vectorLayers"',
        "function renderVectorLayers()",
        "function fitBounds(bounds)",
        'type==="Point"',
        'type==="LineString"',
        'type==="Polygon"',
        "vectorLayers=Array.isArray(multi.vectorLayers)",
    ):
        assert expected in html


def test_geo_c3a2_imported_layers_remain_local_and_do_not_touch_case_database():
    layers = _read(MAP_LAYERS)
    bridge = _read(GEO_BRIDGE)

    assert "DATA_DIR / \"map_layers\"" in layers
    assert "MAX_VECTOR_FILE_BYTES = 5_000_000" in layers
    assert "MAX_VECTOR_FEATURES = 5_000" in layers
    assert "MAX_VECTOR_COORDINATES = 100_000" in layers

    for source in (layers, bridge):
        for forbidden in (
            "create_entity(",
            "create_evidence(",
            ".commit(",
            "session.add(",
        ):
            assert forbidden not in source
