from __future__ import annotations

from pathlib import Path

from app.geo_intelligence.map_sources import (
    BUILTIN_MAP_SOURCES,
    MapSourceRegistry,
)


MAP_SOURCES = Path("app/geo_intelligence/map_sources.py")
TOOLBAR_QML = Path("app/interface/desktop/qml/components/MapSourceToolbar.qml")
BROWSER_QML = Path("app/interface/desktop/qml/components/MapSourceBrowserDialog.qml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_geo_c3a3_curated_catalog_contains_useful_global_sources():
    sources = {source.id: source for source in BUILTIN_MAP_SOURCES}

    assert {
        "osm_standard",
        "opentopomap",
        "nasa_blue_marble",
        "nasa_aster_elevation",
        "nasa_viirs_city_lights",
        "openseamap_seamarks",
        "openrailwaymap_reference",
        "local_schematic",
        "sentinel_selected",
    }.issubset(sources)

    assert sources["opentopomap"].kind == "xyz"
    assert sources["opentopomap"].category == "topographic"
    assert sources["opentopomap"].metadata["curated"] is True

    assert sources["nasa_blue_marble"].kind == "wms"
    assert sources["nasa_blue_marble"].wms_layers == "BlueMarble_ShadedRelief"
    assert sources["nasa_blue_marble"].wms_version == "1.1.1"

    assert sources["nasa_aster_elevation"].wms_layers == "ASTER_GDEM_Color_Index"
    assert sources["nasa_viirs_city_lights"].wms_layers == "VIIRS_CityLights_2012"

    assert sources["openseamap_seamarks"].metadata["role"] == "overlay"
    assert sources["openseamap_seamarks"].metadata["primarySelectable"] is False

    railway = sources["openrailwaymap_reference"]
    assert railway.enabled is False
    assert railway.metadata["policyRestricted"] is True
    assert railway.metadata["primarySelectable"] is False


def test_geo_c3a3_curated_sources_keep_attribution_and_no_prefetch():
    sources = {
        source.id: source
        for source in BUILTIN_MAP_SOURCES
        if source.metadata.get("curated")
    }

    assert sources

    for source in sources.values():
        assert source.attribution
        assert source.terms_url.startswith("http")
        assert source.metadata["prefetchAllowed"] is False
        assert source.metadata["cachePolicy"] == "http_headers"


def test_geo_c3a3_registry_payload_includes_disabled_reference_for_browser(tmp_path):
    registry = MapSourceRegistry(
        storage_path=tmp_path / "map_sources.json"
    )
    payload = {
        row["id"]: row
        for row in registry.payload()
    }

    assert "openrailwaymap_reference" in payload
    assert payload["openrailwaymap_reference"]["enabled"] is False
    assert payload["openrailwaymap_reference"]["metadata"]["policyRestricted"] is True


def test_geo_c3a3_toolbar_filters_disabled_and_overlay_only_primary_sources():
    qml = _read(TOOLBAR_QML)

    assert "function sourceAvailable(source)" in qml
    assert "if (!Boolean((source || {}).enabled))" in qml
    assert "function primarySelectable(source)" in qml
    assert "metadata.primarySelectable !== false" in qml
    assert "if (!root.primarySelectable(source))" in qml


def test_geo_c3a3_browser_has_categories_descriptions_roles_and_policy_notes():
    qml = _read(BROWSER_QML)

    for expected in (
        'property string categoryFilter: "all"',
        '{ key: "streets", label: "Streets" }',
        '{ key: "topographic", label: "Topo" }',
        '{ key: "earth", label: "Earth" }',
        '{ key: "maritime", label: "Maritime" }',
        '{ key: "infrastructure", label: "Infrastructure" }',
        '{ key: "satellite", label: "Satellite" }',
        '{ key: "custom", label: "Custom" }',
        "metadata.description",
        "metadata.provider",
        "policyNote",
        "policyRestricted",
        'return "REFERENCE"',
    ):
        assert expected in qml


def test_geo_c3a3_browser_prevents_overlay_only_source_from_becoming_primary():
    qml = _read(BROWSER_QML)

    assert "function primarySelectable(source)" in qml
    assert "&& root.primarySelectable(sourceRow.modelData)" in qml
    assert 'text: "Compare"' in qml
