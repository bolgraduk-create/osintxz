from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from app.geo_intelligence.providers.copernicus_sentinel2 import (
    CopernicusSentinel2CatalogProvider,
    CopernicusSentinel2Renderer,
    Sentinel2RenderRequest,
    Sentinel2SceneSearchRequest,
)
from app.intelligence_sources.builtin_sources import register_massive_remote_sources
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.coverage import SourceImplementationStatus


def _stac_scene(
    scene_id: str,
    acquired_at: str,
    cloud_cover: float,
    *,
    thumbnail_host: str = "stac.dataspace.copernicus.eu",
) -> dict:
    return {
        "type": "Feature",
        "id": scene_id,
        "bbox": [30.0, 46.0, 31.0, 47.0],
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [30.0, 46.0],
                [31.0, 46.0],
                [31.0, 47.0],
                [30.0, 47.0],
                [30.0, 46.0],
            ]],
        },
        "properties": {
            "datetime": acquired_at,
            "eo:cloud_cover": cloud_cover,
            "platform": "sentinel-2c",
        },
        "assets": {
            "thumbnail": {
                "href": (
                    f"https://{thumbnail_host}/previews/{scene_id}.jpg"
                ),
                "type": "image/jpeg",
                "roles": ["thumbnail"],
            },
        },
        "links": [
            {
                "rel": "self",
                "href": (
                    "https://stac.dataspace.copernicus.eu/v1/"
                    f"collections/sentinel-2-l2a/items/{scene_id}"
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
        Sentinel2SceneSearchRequest(latitude=91, longitude=30)

    with pytest.raises(ValueError):
        Sentinel2SceneSearchRequest(
            latitude=46,
            longitude=30,
            max_cloud_cover=101,
        )


def test_geo_c2_stac_query_is_point_scoped_bounded_and_l2a():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://stac.dataspace.copernicus.eu/v1/search"
        body = __import__("json").loads(request.content)

        assert body["collections"] == ["sentinel-2-l2a"]
        assert body["intersects"] == {
            "type": "Point",
            "coordinates": [30.7233, 46.4825],
        }
        assert body["datetime"] == (
            "2026-08-03T00:00:00Z/2026-08-07T23:59:59Z"
        )
        assert body["query"]["eo:cloud_cover"]["lte"] == 40
        assert body["sortby"] == [
            {
                "field": "properties.datetime",
                "direction": "desc",
            }
        ]
        assert body["limit"] == 12

        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
            },
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


def test_geo_c2_stac_parses_scene_metadata_and_safe_thumbnail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _stac_scene(
                        "S2C_TEST_SCENE",
                        "2026-08-05T10:00:00Z",
                        12.5,
                    )
                ],
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

    assert scene["id"] == "S2C_TEST_SCENE"
    assert scene["productType"] == "S2MSI2A"
    assert scene["platform"] == "sentinel-2c"
    assert scene["cloudCover"] == 12.5
    assert scene["bbox"] == [30.0, 46.0, 31.0, 47.0]
    assert scene["quicklookUrl"].startswith(
        "https://stac.dataspace.copernicus.eu/"
    )
    assert scene["catalog"] == "STAC 1.1"
    assert scene["transient"] is True


def test_geo_c2_stac_drops_untrusted_thumbnail_but_keeps_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _stac_scene(
                        "unsafe-preview",
                        "2026-08-05T10:00:00Z",
                        10.0,
                        thumbnail_host="example.com",
                    )
                ],
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


def test_geo_c2_stac_target_date_ranking_precedes_cloud_cover():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _stac_scene(
                        "later-clear",
                        "2026-08-06T10:00:00Z",
                        1.0,
                    ),
                    _stac_scene(
                        "target-cloudier",
                        "2026-08-05T10:00:00Z",
                        20.0,
                    ),
                ],
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

    assert result["scenes"][0]["id"] == "target-cloudier"


def test_geo_c2_stac_rate_limit_is_isolated():
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


def test_geo_c2_renderer_requires_credentials_without_network():
    renderer = CopernicusSentinel2Renderer(
        client_id="",
        client_secret="",
    )

    result = renderer.render(
        Sentinel2RenderRequest(
            scene={
                "id": "scene",
                "acquiredAt": "2026-08-05T10:00:00Z",
            },
            latitude=46.4825,
            longitude=30.7233,
        )
    )

    assert result["status"] == "skipped"
    assert result["configured"] is False


def test_geo_c2_renderer_gets_token_and_requests_bounded_true_color(tmp_path):
    token_requests = []
    process_requests = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_requests.append(request)
        body = request.content.decode("utf-8")
        assert "grant_type=client_credentials" in body
        assert "client_id=test-client" in body
        assert "client_secret=test-secret" in body
        return httpx.Response(
            200,
            json={
                "access_token": "test-access-token",
                "expires_in": 600,
            },
        )

    def process_handler(request: httpx.Request) -> httpx.Response:
        process_requests.append(request)
        assert request.headers["authorization"] == "Bearer test-access-token"
        body = __import__("json").loads(request.content)

        bbox = body["input"]["bounds"]["bbox"]
        assert len(bbox) == 4
        assert bbox[0] < 30.7233 < bbox[2]
        assert bbox[1] < 46.4825 < bbox[3]

        data_filter = body["input"]["data"][0]["dataFilter"]
        assert data_filter["timeRange"] == {
            "from": "2026-08-05T00:00:00Z",
            "to": "2026-08-05T23:59:59Z",
        }
        assert data_filter["mosaickingOrder"] == "leastCC"
        assert body["output"]["width"] == 768
        assert body["output"]["height"] == 768
        assert body["output"]["responses"][0]["format"]["type"] == "image/png"
        assert "B04" in body["evalscript"]
        assert "B03" in body["evalscript"]
        assert "B02" in body["evalscript"]
        assert "dataMask" in body["evalscript"]

        return httpx.Response(
            200,
            content=b"\x89PNG\r\n\x1a\nFAKE",
            headers={"content-type": "image/png"},
        )

    renderer = CopernicusSentinel2Renderer(
        client_id="test-client",
        client_secret="test-secret",
        token_transport=httpx.MockTransport(token_handler),
        process_transport=httpx.MockTransport(process_handler),
        cache_dir=tmp_path,
    )

    result = renderer.render(
        Sentinel2RenderRequest(
            scene={
                "id": "scene-1",
                "acquiredAt": "2026-08-05T10:00:00Z",
                "cloudCover": 12.4,
            },
            latitude=46.4825,
            longitude=30.7233,
            radius_m=3_000,
        )
    )

    assert len(token_requests) == 1
    assert len(process_requests) == 1
    assert result["status"] == "completed"
    assert result["configured"] is True
    assert result["renderMode"] == "true_color"
    assert result["persisted"] is False
    assert result["transient"] is True
    assert Path(result["renderPath"]).read_bytes().startswith(b"\x89PNG")
    assert result["imageBytes"] < renderer.MAX_IMAGE_BYTES


def test_geo_c2_sources_are_active_with_correct_access_modes():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)

    discovery = catalog.get("copernicus_sentinel2_catalog")
    renderer = catalog.get("copernicus_sentinel2_process")

    assert discovery is not None
    assert renderer is not None

    assert discovery.default_enabled is True
    assert discovery.requires_credentials is False
    assert "stac" in discovery.capabilities
    assert "satellite_scene" in discovery.capabilities

    assert renderer.default_enabled is True
    assert renderer.requires_credentials is True
    assert "true_color" in renderer.capabilities
    assert "satellite_render" in renderer.capabilities

    assert (
        coverage.get("copernicus_sentinel2_catalog").status
        is SourceImplementationStatus.ACTIVE
    )
    assert (
        coverage.get("copernicus_sentinel2_process").status
        is SourceImplementationStatus.ACTIVE
    )


def test_geo_c2_bridge_and_map_ui_support_true_color_and_hybrid():
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
        "def satelliteRenderingAvailable(self)",
        "def satelliteRenderBusy(self)",
        "def runSatelliteSearch(",
        "def renderSatelliteScene(",
        "SatelliteSceneRenderWorker",
        "QUrl.fromLocalFile",
    ):
        assert expected in bridge

    for expected in (
        "geoBridge.satelliteData",
        "geoBridge.runSatelliteSearch(",
        "geoBridge.renderSatelliteScene(",
        'text: "SATELLITE · SENTINEL-2"',
        '"Find Sentinel-2 scenes"',
        '"Render True Color"',
        'text: "Satellite"',
        'text: "Hybrid"',
        "root.selectedSatelliteScene.renderUrl",
        "item.satelliteScene = Qt.binding",
        "CDSE_CLIENT_ID",
        "CDSE_CLIENT_SECRET",
    ):
        assert expected in qml

    assert "property var satelliteScene" in web_qml
    assert "satelliteScene: root.satelliteScene" in web_qml

    assert 'id="satellite"' in html
    assert "function renderSatellite()" in html
    assert "function fitSatellite()" in html
    assert 'baseMode === "satellite"' in html
    assert 'baseMode === "hybrid"' in html
    assert "satelliteDisplayUrl(scene)" in html
    assert "scene.renderUrl || scene.quicklookUrl" in html


def test_geo_c2_does_not_auto_persist_or_download_full_products():
    provider = Path(
        "app/geo_intelligence/providers/copernicus_sentinel2.py"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/geo_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert "/$zip" not in provider
    assert "full SAFE/ZIP products are never downloaded automatically" in qml

    for source in (provider, bridge):
        for forbidden in (
            "create_entity(",
            "create_evidence(",
            "update_metadata(",
            ".commit(",
        ):
            assert forbidden not in source


def test_geo_c2_secret_values_are_not_exposed_to_qml():
    qml = Path(
        "app/interface/desktop/qml/pages/MapWorkspace.qml"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/satellite_scene_render_worker.py"
    ).read_text(encoding="utf-8")

    # The UI may name the environment variable so the analyst knows what to
    # configure, but it must never read or receive the underlying secret value.
    assert "CDSE_CLIENT_SECRET" in qml
    assert "settings.cdse_client_secret" not in qml
    assert "get_secret_value()" not in qml
    assert "client_secret =" not in qml.lower()

    assert "get_secret_value()" in worker
    assert "settings.cdse_client_secret" in worker
