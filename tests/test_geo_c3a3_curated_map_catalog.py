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
        '"Search maps by name, type, category..."',
        '"XYZ · WMS · WMTS · Sentinel"',
    ):
        assert expected in qml


def test_geo_c3a3_nasa_and_usgs_catalog_pack():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert set(sources) >= {
        "nasa_blue_marble",
        "nasa_blue_marble_relief",
        "usgs_topo",
        "usgs_imagery",
        "usgs_shaded_relief",
        "usgs_hydro",
    }

    blue = sources["nasa_blue_marble"]
    assert blue.region == "World"
    assert blue.provider == "NASA GIBS"
    assert blue.category == "satellite"
    assert blue.max_zoom == 8
    assert "BlueMarble_NextGeneration" in blue.url
    assert blue.requires_api_key is False

    relief = sources["nasa_blue_marble_relief"]
    assert relief.category == "terrain"
    assert "BlueMarble_ShadedRelief_Bathymetry" in relief.url

    topo = sources["usgs_topo"]
    assert topo.region == "United States"
    assert topo.provider == "U.S. Geological Survey"
    assert "USGSTopo/MapServer/tile/{z}/{y}/{x}" in topo.url

    imagery = sources["usgs_imagery"]
    assert imagery.category == "satellite"
    assert "USGSImageryOnly/MapServer/tile/{z}/{y}/{x}" in imagery.url

    shaded = sources["usgs_shaded_relief"]
    assert shaded.category == "terrain"
    assert shaded.max_zoom == 7
    assert "USGSShadedReliefOnly/MapServer/tile/{z}/{y}/{x}" in shaded.url

    hydro = sources["usgs_hydro"]
    assert hydro.category == "hydrography"
    assert hydro.primary_supported is False
    assert hydro.metadata["overlayOnly"] is True
    assert "USGSHydroCached/MapServer/tile/{z}/{y}/{x}" in hydro.url


def test_geo_c3a3_poland_and_germany_country_packs():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert set(sources) >= {
        "pl_geoportal_ortho",
        "de_basemap_raster_color",
    }

    poland = sources["pl_geoportal_ortho"]
    assert poland.region == "Poland"
    assert poland.provider == "Główny Urząd Geodezji i Kartografii"
    assert poland.category == "satellite"
    assert "LAYER=ORTOFOTOMAPA" in poland.url
    assert "TILEMATRIXSET=EPSG:3857" in poland.url
    assert "TILEMATRIX=EPSG:3857:{z}" in poland.url
    assert "TILEROW={y}" in poland.url
    assert "TILECOL={x}" in poland.url
    assert poland.metadata["catalogPack"] == "poland"

    germany = sources["de_basemap_raster_color"]
    assert germany.region == "Germany"
    assert germany.provider == "BKG / GeoBasis-DE"
    assert germany.category == "streets"
    assert "GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png" in germany.url
    assert germany.metadata["catalogPack"] == "germany"


def test_geo_c3a3_france_country_pack():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert set(sources) >= {
        "fr_ign_plan_v2",
        "fr_ign_ortho",
    }

    plan = sources["fr_ign_plan_v2"]
    assert plan.region == "France"
    assert plan.provider == "IGN France / Géoplateforme"
    assert plan.category == "streets"
    assert "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" in plan.url
    assert "TILEMATRIXSET=PM" in plan.url

    ortho = sources["fr_ign_ortho"]
    assert ortho.region == "France"
    assert ortho.category == "satellite"
    assert "ORTHOIMAGERY.ORTHOPHOTOS" in ortho.url
    assert "FORMAT=image/jpeg" in ortho.url
