from pathlib import Path

from app.geo_intelligence.map_sources import BUILTIN_MAP_SOURCES


MAP_SOURCES = Path("app/geo_intelligence/map_sources.py")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
BROWSER_QML = Path("app/interface/desktop/qml/components/MapSourceBrowserDialog.qml")
MAP_QML = Path("app/interface/desktop/qml/pages/MapWorkspace.qml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_c3a3_curated_world_catalog_has_initial_source_pack():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert set(sources) >= {
        "osm_standard",
        "opentopomap",
        "openseamap_seamarks",
        "openrailwaymap_standard",
        "local_schematic",
        "sentinel_selected",
    }

    topo = sources["opentopomap"]
    assert topo.kind == "xyz"
    assert topo.category == "terrain"
    assert topo.region == "World"
    assert topo.provider == "OpenTopoMap"
    assert topo.primary_supported is True
    assert topo.url == "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"

    sea = sources["openseamap_seamarks"]
    assert sea.category == "marine"
    assert sea.primary_supported is False
    assert sea.metadata["overlayOnly"] is True
    assert sea.url == "https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"

    railway = sources["openrailwaymap_standard"]
    assert railway.category == "transport"
    assert railway.primary_supported is False
    assert railway.metadata["overlayOnly"] is True
    assert railway.metadata["tilePixelRatio"] == 2
    assert railway.url == (
        "https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"
    )


def test_geo_c3a3_source_payload_exposes_catalog_metadata():
    source = next(
        item for item in BUILTIN_MAP_SOURCES
        if item.id == "opentopomap"
    )
    payload = source.to_payload()

    assert payload["region"] == "World"
    assert payload["provider"] == "OpenTopoMap"
    assert "topographic" in payload["tags"]
    assert payload["primarySupported"] is True
    assert payload["requiresApiKey"] is False
    assert payload["requiresOptIn"] is False


def test_geo_c3a3_overlay_sources_are_not_selectable_as_primary():
    toolbar = _read(TOOLBAR_QML)
    browser = _read(BROWSER_QML)
    workspace = _read(MAP_QML)

    assert "if (source.primarySupported === false)" in toolbar
    assert "sourceRow.modelData.primarySupported !== false" in browser
    assert "if (source.primarySupported === false)" in workspace


def test_geo_c3a3_browser_searches_catalog_metadata():
    qml = _read(BROWSER_QML)

    for expected in (
        "String(source.region || \"\")",
        "String(source.provider || \"\")",
        "String((source.tags || []).join(\" \"))",
        '"Search maps by name, region, provider, tag..."',
        '"WORLD CATALOG · XYZ · WMS · WMTS · Sentinel"',
    ):
        assert expected in qml
