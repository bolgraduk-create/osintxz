from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from app.geo_intelligence.contracts import (
    GeoEnrichmentRequest,
    GeoPoint,
    GeoProviderStatus,
)
from app.geo_intelligence.providers.open_meteo import (
    OpenMeteoHistoricalProvider,
)
from app.geo_intelligence.providers.overpass import (
    OverpassNearbyProvider,
)
from app.geo_intelligence.service import GeoIntelligenceService
from app.intelligence_sources.builtin_sources import (
    register_massive_remote_sources,
)
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.coverage import SourceImplementationStatus


def test_geo_c1_contract_validates_coordinates_radius_and_date():
    request = GeoEnrichmentRequest(
        point=GeoPoint(latitude=46.4825, longitude=30.7233),
        radius_m=750,
        historical_date=date(2026, 8, 5),
    )
    assert request.radius_m == 750
    assert request.historical_date == date(2026, 8, 5)

    with pytest.raises(ValueError):
        GeoPoint(latitude=100, longitude=30)

    with pytest.raises(ValueError):
        GeoEnrichmentRequest(
            point=GeoPoint(latitude=46.4, longitude=30.7),
            radius_m=50,
        )


def test_overpass_provider_posts_bounded_query_and_maps_node_and_way():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = parse_qs(request.content.decode("utf-8"))
        query = body["data"][0]
        assert "around:750,46.4825000,30.7233000" in query
        assert '["amenity"]' in query
        assert '["tourism"]' in query
        assert "out center tags qt;" in query
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 101,
                        "lat": 46.483,
                        "lon": 30.724,
                        "tags": {
                            "name": "Test Cafe",
                            "amenity": "cafe",
                            "addr:street": "Example Street",
                            "phone": "+380000000000",
                        },
                    },
                    {
                        "type": "way",
                        "id": 202,
                        "center": {"lat": 46.484, "lon": 30.725},
                        "tags": {
                            "name": "Test Hotel",
                            "tourism": "hotel",
                        },
                    },
                ]
            },
        )

    provider = OverpassNearbyProvider(
        transport=httpx.MockTransport(handler)
    )
    result = provider.enrich(
        GeoEnrichmentRequest(
            point=GeoPoint(46.4825, 30.7233),
            radius_m=750,
            poi_limit=20,
        )
    )

    assert result.status is GeoProviderStatus.SUCCESS
    assert len(result.records) == 2
    assert result.records[0]["title"] == "Test Cafe"
    assert result.records[0]["category"] == "cafe"
    assert result.records[0]["sourceUrl"] == (
        "https://www.openstreetmap.org/node/101"
    )
    assert result.records[1]["latitude"] == 46.484
    assert result.metadata["read_only"] is True


def test_overpass_provider_isolates_rate_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"remark": "rate limited"})

    result = OverpassNearbyProvider(
        transport=httpx.MockTransport(handler)
    ).enrich(
        GeoEnrichmentRequest(
            point=GeoPoint(46.4825, 30.7233),
        )
    )

    assert result.status is GeoProviderStatus.PARTIAL
    assert result.metadata["rate_limited"] is True
    assert result.metadata["retryable"] is True


def test_open_meteo_skips_when_date_is_not_requested():
    result = OpenMeteoHistoricalProvider().enrich(
        GeoEnrichmentRequest(
            point=GeoPoint(46.4825, 30.7233),
        )
    )

    assert result.status is GeoProviderStatus.SKIPPED
    assert result.records == []


def test_open_meteo_requests_one_day_and_maps_weather():
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert params["latitude"] == "46.4825"
        assert params["longitude"] == "30.7233"
        assert params["start_date"] == "2026-08-05"
        assert params["end_date"] == "2026-08-05"
        assert params["timezone"] == "UTC"
        assert "temperature_2m" in params["hourly"]
        assert "sunrise" in params["daily"]
        return httpx.Response(
            200,
            json={
                "latitude": 46.48,
                "longitude": 30.72,
                "elevation": 42.0,
                "timezone": "UTC",
                "daily": {
                    "time": ["2026-08-05"],
                    "temperature_2m_max": [29.4],
                    "temperature_2m_min": [20.1],
                    "precipitation_sum": [1.2],
                    "snowfall_sum": [0.0],
                    "sunrise": ["2026-08-05T02:35"],
                    "sunset": ["2026-08-05T17:25"],
                },
                "daily_units": {
                    "temperature_2m_max": "°C",
                    "temperature_2m_min": "°C",
                    "precipitation_sum": "mm",
                },
                "hourly": {
                    "time": ["2026-08-05T00:00", "2026-08-05T01:00"],
                    "temperature_2m": [22.0, 21.5],
                    "relative_humidity_2m": [70, 73],
                    "precipitation": [0.0, 0.1],
                    "snowfall": [0.0, 0.0],
                    "weather_code": [1, 2],
                    "cloud_cover": [20, 35],
                    "visibility": [24000, 22000],
                    "wind_speed_10m": [8.0, 7.5],
                    "wind_direction_10m": [120, 125],
                },
            },
        )

    provider = OpenMeteoHistoricalProvider(
        transport=httpx.MockTransport(handler)
    )
    result = provider.enrich(
        GeoEnrichmentRequest(
            point=GeoPoint(46.4825, 30.7233),
            historical_date=date(2026, 8, 5),
        )
    )

    assert result.status is GeoProviderStatus.SUCCESS
    assert result.summary["temperature_2m_max"] == 29.4
    assert result.summary["sunrise"] == "2026-08-05T02:35"
    assert len(result.records) == 2
    assert result.records[0]["temperature_2m"] == 22.0
    assert result.metadata["read_only"] is True


def test_geo_service_combines_providers_without_persistence():
    class Overpass:
        source_code = "overpass_osm"

        def enrich(self, request):
            from app.geo_intelligence.contracts import GeoProviderResult
            return GeoProviderResult(
                source=self.source_code,
                status=GeoProviderStatus.SUCCESS,
                records=[
                    {
                        "id": "osm:node:1",
                        "kind": "poi",
                        "title": "POI",
                        "latitude": request.point.latitude,
                        "longitude": request.point.longitude,
                    }
                ],
            )

    class Weather:
        source_code = "open_meteo_historical"

        def enrich(self, request):
            from app.geo_intelligence.contracts import GeoProviderResult
            return GeoProviderResult(
                source=self.source_code,
                status=GeoProviderStatus.SUCCESS,
                summary={
                    "date": request.historical_date.isoformat(),
                    "temperature_2m_max": 20,
                },
            )

    result = GeoIntelligenceService(
        overpass=Overpass(),
        weather=Weather(),
    ).enrich(
        latitude=46.4825,
        longitude=30.7233,
        radius_m=750,
        historical_date="2026-08-05",
    )

    assert result["status"] == "completed"
    assert result["summary"]["nearbyPlaces"] == 1
    assert result["summary"]["weatherAvailable"] is True
    assert result["transient"] is True
    assert result["persisted"] is False


def test_geo_c1_sources_are_active_in_source_catalog():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)

    overpass = catalog.get("overpass_osm")
    weather = catalog.get("open_meteo_historical")

    assert overpass is not None
    assert weather is not None
    assert overpass.default_enabled is True
    assert weather.default_enabled is True
    assert "nearby_poi" in overpass.capabilities
    assert "historical_weather" in weather.capabilities

    assert coverage.get("overpass_osm").status is SourceImplementationStatus.ACTIVE
    assert coverage.get("open_meteo_historical").status is SourceImplementationStatus.ACTIVE


def test_geo_c1_desktop_bridge_is_exposed_and_map_is_wired():
    desktop_app = Path(
        "app/interface/desktop/desktop_app.py"
    ).read_text(encoding="utf-8")
    bridges = Path(
        "app/interface/desktop/bridges/__init__.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert "GeoBridge" in desktop_app
    assert '"geoBridge"' in desktop_app
    assert "GeoBridge" in bridges

    for expected in (
        "geoBridge.runData",
        "geoBridge.runEnrichment(",
        'text: "LIVE GEO ENRICHMENT"',
        'text: "Nearby POI"',
        'placeholderText: "Latitude"',
        'placeholderText: "Longitude"',
        'placeholderText: "YYYY-MM-DD (optional)"',
        '"OpenStreetMap / Overpass"',
        '"HISTORICAL WEATHER · "',
        '"TRANSIENT"',
    ):
        assert expected in qml


def test_geo_c1_map_does_not_persist_live_enrichment():
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")
    geo_service = Path(
        "app/geo_intelligence/service.py"
    ).read_text(encoding="utf-8")

    assert "not persisted" in qml
    assert '"persisted": False' in geo_service

    for forbidden in (
        "create_entity(",
        "create_evidence(",
        "update_metadata(",
        ".commit(",
    ):
        assert forbidden not in geo_service
