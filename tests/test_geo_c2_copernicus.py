from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from app.geo_intelligence.providers.copernicus_sentinel2 import (
    CopernicusSentinel2CatalogProvider,
    Sentinel2SceneSearchRequest,
)
from app.intelligence_sources.builtin_sources import (
    register_massive_remote_sources,
)
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.coverage import SourceImplementationStatus


def _scene(
    scene_id: str,
    acquired_at: str,
    cloud_cover: float,
    *,
    quicklook_host: str = "catalogue.dataspace.copernicus.eu",
) -> dict:
    return {
        "Id": scene_id,
        "Name": f"S2A_MSIL2A_{acquired_at[:10].replace('-', '')}T100000_TEST.SAFE",
        "Online": True,
        "ContentLength": 123456,
        "S3Path": f"/eodata/Sentinel-2/{scene_id}",
        "ContentDate": {
            "Start": acquired_at,
            "End": acquired_at,
        },
        "GeoFootprint": {
            "type": "Polygon",
            "coordinates": [
                [
                    [30.0, 46.0],
                    [31.0, 46.0],
                    [31.0, 47.0],
                    [30.0, 47.0],
                    [30.0, 46.0],
                ]
            ],
        },
        "Attributes": [
            {
                "Name": "productType",
                "Value": "S2MSI2A",
            },
            {
                "Name": "cloudCover",
                "Value": cloud_cover,
            },
        ],
        "Assets": [
            {
                "Id": f"asset-{scene_id}",
                "Name": "QUICKLOOK",
                "Type": "image/jpeg",
                "DownloadLink": (
                    f"https://{quicklook_host}/odata/v1/"
                    f"Assets(asset-{scene_id})/$value"
                ),
            }
        ],
    }


def test_geo_c2_request_validates_bounds_and_filters():
    request = Sentinel2SceneSearchRequest(
        latitude=46.4825,
        longitude=30.7233,
        target_date=date(2026, 8, 5),
        window_days=5,
        max_cloud_cover=40,
        limit=8,
    )
    assert request.window_days == 5
    assert request.max_cloud_cover == 40

    with pytest.raises(ValueError):
        Sentinel2SceneSearchRequest(
            latitude=91,
            longitude=30,
        )

    with pytest.raises(ValueError):
        Sentinel2SceneSearchRequest(
            latitude=46,
            longitude=30,
            max_cloud_cover=101,
        )


def test_geo_c2_odata_query_is_point_scoped_bounded_and_l2a():
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        query = params["$filter"]

        assert request.method == "GET"
        assert "Collection/Name eq 'SENTINEL-2'" in query
        assert "S2MSI2A" in query
        assert "POINT(30.7233000 46.4825000)" in query
        assert "cloudCover" in query
        assert "Value le 40.00" in query
        assert "ContentDate/Start ge 2026-08-03T00:00:00.000Z" in query
        assert "ContentDate/Start le 2026-08-07T23:59:59.999Z" in query
        assert params["$orderby"] == "ContentDate/Start desc"
        assert params["$top"] == "18"
        assert params["$expand"] == "Assets,Attributes"

        return httpx.Response(
            200,
            json={"value": []},
        )

    provider = CopernicusSentinel2CatalogProvider(
        transport=httpx.MockTransport(handler)
    )
    result = provider.search(
        Sentinel2SceneSearchRequest(
            latitude=46.4825,
            longitude=30.7233,
            target_date=date(2026, 8, 5),
            window_days=2,
            max_cloud_cover=40,
            limit=6,
        )
    )

    assert result["status"] == "completed"
    assert result["scenes"] == []
    assert result["summary"]["sceneCount"] == 0
    assert result["transient"] is True
    assert result["persisted"] is False


def test_geo_c2_parses_quicklook_bbox_and_scene_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    _scene(
                        "scene-1",
                        "2026-08-05T10:00:00.000Z",
                        12.5,
                    )
                ]
            },
        )

    result = CopernicusSentinel2CatalogProvider(
        transport=httpx.MockTransport(handler)
    ).search(
        Sentinel2SceneSearchRequest(
            latitude=46.4825,
            longitude=30.7233,
            target_date=date(2026, 8, 5),
        )
    )

    scene = result["scenes"][0]

    assert scene["id"] == "scene-1"
    assert scene["productType"] == "S2MSI2A"
    assert scene["cloudCover"] == 12.5
    assert scene["bbox"] == [30.0, 46.0, 31.0, 47.0]
    assert scene["quicklookUrl"].startswith(
        "https://catalogue.dataspace.copernicus.eu/"
    )
    assert scene["source"] == "Copernicus Data Space Ecosystem"
    assert scene["transient"] is True


def test_geo_c2_ranks_target_date_before_lower_cloud_nearby_date():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    _scene(
                        "later-clear",
                        "2026-08-06T10:00:00.000Z",
                        1.0,
                    ),
                    _scene(
                        "target-cloudier",
                        "2026-08-05T10:00:00.000Z",
                        20.0,
                    ),
                    _scene(
                        "earlier-clear",
                        "2026-08-04T10:00:00.000Z",
                        2.0,
                    ),
                ]
            },
        )

    result = CopernicusSentinel2CatalogProvider(
        transport=httpx.MockTransport(handler)
    ).search(
        Sentinel2SceneSearchRequest(
            latitude=46.4825,
            longitude=30.7233,
            target_date=date(2026, 8, 5),
            max_cloud_cover=40,
        )
    )

    assert result["scenes"][0]["id"] == "target-cloudier"


def test_geo_c2_drops_untrusted_quicklook_url_but_keeps_scene_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "value": [
                    _scene(
                        "unsafe-preview",
                        "2026-08-05T10:00:00.000Z",
                        10.0,
                        quicklook_host="example.com",
                    )
                ]
            },
        )

    result = CopernicusSentinel2CatalogProvider(
        transport=httpx.MockTransport(handler)
    ).search(
        Sentinel2SceneSearchRequest(
            latitude=46.4825,
            longitude=30.7233,
        )
    )

    assert len(result["scenes"]) == 1
    assert result["scenes"][0]["quicklookUrl"] == ""
    assert result["summary"]["quicklookCount"] == 0


def test_geo_c2_rate_limit_is_isolated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "rate limited"})

    result = CopernicusSentinel2CatalogProvider(
        transport=httpx.MockTransport(handler)
    ).search(
        Sentinel2SceneSearchRequest(
            latitude=46.4825,
            longitude=30.7233,
        )
    )

    assert result["status"] == "partial"
    assert result["rateLimited"] is True
    assert result["retryable"] is True
    assert result["scenes"] == []


def test_geo_c2_source_is_active_in_source_catalog():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)

    source = catalog.get("copernicus_sentinel2_catalog")

    assert source is not None
    assert source.default_enabled is True
    assert source.requires_credentials is False
    assert "satellite_scene" in source.capabilities
    assert "satellite_quicklook" in source.capabilities
    assert (
        coverage.get("copernicus_sentinel2_catalog").status
        is SourceImplementationStatus.ACTIVE
    )


def test_geo_c2_bridge_and_map_ui_are_wired_without_auto_persistence():
    bridge = Path(
        "app/interface/desktop/bridges/geo_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")
    web_qml = Path(
        "app/interface/desktop/qml/components/InteractiveMapView.qml"
    ).read_text(encoding="utf-8")
    html = Path(
        "app/interface/desktop/qml/map/map_engine.html"
    ).read_text(encoding="utf-8")

    for expected in (
        "def satelliteData(self)",
        "def satelliteBusy(self)",
        "def runSatelliteSearch(",
        "def selectSatelliteScene(",
        "SatelliteSceneSearchWorker",
    ):
        assert expected in bridge

    for expected in (
        "geoBridge.satelliteData",
        "geoBridge.runSatelliteSearch(",
        "geoBridge.selectSatelliteScene(",
        'text: "SATELLITE · SENTINEL-2"',
        'text: "Find Sentinel-2 scenes"',
        'text: "Satellite"',
        "root.selectedSatelliteScene.quicklookUrl",
        "item.satelliteScene = Qt.binding",
    ):
        assert expected in qml

    assert "property var satelliteScene" in web_qml
    assert "satelliteScene: root.satelliteScene" in web_qml
    assert 'id="satellite"' in html
    assert "function renderSatellite()" in html
    assert "function fitSatellite()" in html
    assert 'baseMode === "satellite"' in html

    for forbidden in (
        "create_entity(",
        "create_evidence(",
        "update_metadata(",
        ".commit(",
    ):
        assert forbidden not in bridge


def test_geo_c2_full_product_download_is_not_implemented():
    provider = Path(
        "app/geo_intelligence/providers/copernicus_sentinel2.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert "/$zip" not in provider
    assert "/$value" in provider  # only bounded quicklook asset fallback
    assert "full products are never downloaded automatically" in qml
