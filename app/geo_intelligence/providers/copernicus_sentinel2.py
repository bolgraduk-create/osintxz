from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True, slots=True)
class Sentinel2SceneSearchRequest:
    latitude: float
    longitude: float
    target_date: date | None = None
    window_days: int = 5
    max_cloud_cover: int = 40
    limit: int = 8
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        latitude = float(self.latitude)
        longitude = float(self.longitude)
        if not -90.0 <= latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90.")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("longitude must be between -180 and 180.")

        window_days = int(self.window_days)
        if not 0 <= window_days <= 30:
            raise ValueError("window_days must be 0..30.")

        max_cloud_cover = int(self.max_cloud_cover)
        if not 0 <= max_cloud_cover <= 100:
            raise ValueError("max_cloud_cover must be 0..100.")

        limit = int(self.limit)
        if not 1 <= limit <= 12:
            raise ValueError("limit must be 1..12.")

        timeout_seconds = int(self.timeout_seconds)
        if not 3 <= timeout_seconds <= 45:
            raise ValueError("timeout_seconds must be 3..45.")

        if self.target_date is not None and self.target_date > date.today():
            raise ValueError("Satellite target date cannot be in the future.")

        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)
        object.__setattr__(self, "window_days", window_days)
        object.__setattr__(self, "max_cloud_cover", max_cloud_cover)
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "timeout_seconds", timeout_seconds)


class CopernicusSentinel2CatalogProvider:
    """No-auth Sentinel-2 L2A scene discovery through CDSE OData."""

    API = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    MAX_BYTES = 3_000_000

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        endpoint: str | None = None,
        user_agent: str = "OSINTXZ/0.1 GEO Copernicus",
    ) -> None:
        self.transport = transport
        self.endpoint = str(endpoint or self.API).strip()
        self.user_agent = user_agent

    @property
    def source_code(self) -> str:
        return "copernicus_sentinel2_catalog"

    def search(
        self,
        request: Sentinel2SceneSearchRequest,
    ) -> dict[str, Any]:
        start_date, end_date = self._date_window(request)
        filters = [
            "Collection/Name eq 'SENTINEL-2'",
            (
                "Attributes/OData.CSC.StringAttribute/any("
                "att:att/Name eq 'productType' and "
                "att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')"
            ),
            (
                "OData.CSC.Intersects(area=geography'"
                "SRID=4326;POINT("
                f"{request.longitude:.7f} {request.latitude:.7f}"
                ")')"
            ),
            (
                "Attributes/OData.CSC.DoubleAttribute/any("
                "att:att/Name eq 'cloudCover' and "
                "att/OData.CSC.DoubleAttribute/Value le "
                f"{float(request.max_cloud_cover):.2f})"
            ),
            f"ContentDate/Start ge {start_date.isoformat()}T00:00:00.000Z",
            f"ContentDate/Start le {end_date.isoformat()}T23:59:59.999Z",
        ]

        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(request.timeout_seconds)),
                transport=self.transport,
                follow_redirects=False,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
            ) as client:
                response = client.get(
                    self.endpoint,
                    params={
                        "$filter": " and ".join(filters),
                        "$orderby": "ContentDate/Start desc",
                        "$top": str(request.limit),
                        "$expand": "Assets,Attributes",
                    },
                )
                if len(response.content) > self.MAX_BYTES:
                    return {
                        "status": "partial",
                        "error": "Copernicus catalogue response exceeded the bounded response size.",
                        "scenes": [],
                        "source": self.source_code,
                        "retryable": True,
                    }
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            return {
                "status": "partial" if code == 429 or code >= 500 else "failed",
                "error": f"Copernicus catalogue HTTP {code}.",
                "scenes": [],
                "source": self.source_code,
                "retryable": code == 429 or code >= 500,
                "rateLimited": code == 429,
            }
        except (httpx.RequestError, ValueError) as exc:
            return {
                "status": "partial",
                "error": str(exc),
                "scenes": [],
                "source": self.source_code,
                "retryable": True,
            }

        rows = payload.get("value", []) if isinstance(payload, dict) else []
        scenes: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            scene = self._scene(row)
            if scene:
                scenes.append(scene)
            if len(scenes) >= request.limit:
                break

        return {
            "status": "completed",
            "error": "",
            "source": self.source_code,
            "scenes": scenes,
            "query": {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "targetDate": (
                    request.target_date.isoformat()
                    if request.target_date is not None
                    else ""
                ),
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "windowDays": request.window_days,
                "maxCloudCover": request.max_cloud_cover,
                "limit": request.limit,
            },
            "summary": {
                "sceneCount": len(scenes),
                "quicklookCount": sum(
                    1 for scene in scenes if scene.get("quicklookUrl")
                ),
            },
            "transient": True,
            "persisted": False,
        }

    @staticmethod
    def _date_window(
        request: Sentinel2SceneSearchRequest,
    ) -> tuple[date, date]:
        if request.target_date is not None:
            return (
                request.target_date - timedelta(days=request.window_days),
                request.target_date + timedelta(days=request.window_days),
            )

        end = date.today()
        return end - timedelta(days=30), end

    @classmethod
    def _scene(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        scene_id = str(row.get("Id") or "").strip()
        name = str(row.get("Name") or "").strip()
        if not scene_id or not name:
            return None

        attributes = cls._attributes(row.get("Attributes"))
        cloud_cover = cls._float_or_none(attributes.get("cloudCover"))
        footprint = row.get("GeoFootprint") or row.get("Footprint")
        bbox = cls._footprint_bbox(footprint)
        quicklook = cls._quicklook(row.get("Assets"))

        content_date = row.get("ContentDate")
        if not isinstance(content_date, dict):
            content_date = {}

        catalogue_url = (
            "https://catalogue.dataspace.copernicus.eu/odata/v1/"
            f"Products({scene_id})"
        )

        return {
            "id": scene_id,
            "name": name,
            "mission": "Sentinel-2",
            "productType": str(attributes.get("productType") or "S2MSI2A"),
            "acquiredAt": str(content_date.get("Start") or ""),
            "endedAt": str(content_date.get("End") or ""),
            "cloudCover": cloud_cover,
            "online": bool(row.get("Online", True)),
            "contentLength": cls._int_or_none(row.get("ContentLength")),
            "s3Path": str(row.get("S3Path") or ""),
            "footprint": footprint if isinstance(footprint, dict) else {},
            "bbox": bbox,
            "quicklookUrl": quicklook.get("url", ""),
            "quicklookAssetId": quicklook.get("id", ""),
            "quicklookName": quicklook.get("name", ""),
            "source": "Copernicus Data Space Ecosystem",
            "sourceUrl": catalogue_url,
            "transient": True,
        }

    @staticmethod
    def _attributes(value: Any) -> dict[str, Any]:
        if not isinstance(value, list):
            return {}

        result: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or "").strip()
            if name:
                result[name] = item.get("Value")
        return result

    @staticmethod
    def _quicklook(value: Any) -> dict[str, str]:
        assets = value if isinstance(value, list) else []
        candidates: list[tuple[int, dict[str, Any]]] = []

        for asset in assets:
            if not isinstance(asset, dict):
                continue

            asset_id = str(asset.get("Id") or "").strip()
            name = str(asset.get("Name") or "").strip()
            asset_type = str(asset.get("Type") or "").strip()
            download = str(
                asset.get("DownloadLink")
                or asset.get("Href")
                or asset.get("href")
                or ""
            ).strip()

            probe = f"{name} {asset_type} {download}".lower()
            score = 0
            if "quicklook" in probe:
                score += 100
            if "thumbnail" in probe or "thumb" in probe:
                score += 80
            if probe.endswith(".jpg") or ".jpg?" in probe or ".jpeg" in probe:
                score += 30
            if probe.endswith(".png") or ".png?" in probe:
                score += 20

            if score <= 0:
                continue

            if not download and asset_id:
                download = (
                    "https://catalogue.dataspace.copernicus.eu/odata/v1/"
                    f"Assets({asset_id})/$value"
                )

            if download and CopernicusSentinel2CatalogProvider._safe_asset_url(download):
                candidates.append(
                    (
                        score,
                        {
                            "id": asset_id,
                            "name": name,
                            "url": download,
                        },
                    )
                )

        if not candidates:
            return {"id": "", "name": "", "url": ""}

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _footprint_bbox(value: Any) -> list[float]:
        if not isinstance(value, dict):
            return []

        coordinates = value.get("coordinates")
        points: list[tuple[float, float]] = []

        def walk(node: Any) -> None:
            if (
                isinstance(node, (list, tuple))
                and len(node) >= 2
                and isinstance(node[0], (int, float))
                and isinstance(node[1], (int, float))
            ):
                points.append((float(node[0]), float(node[1])))
                return

            if isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)

        walk(coordinates)
        if not points:
            return []

        longitudes = [point[0] for point in points]
        latitudes = [point[1] for point in points]
        return [
            min(longitudes),
            min(latitudes),
            max(longitudes),
            max(latitudes),
        ]

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_asset_url(value: str) -> bool:
        try:
            parsed = urlparse(str(value or "").strip())
        except ValueError:
            return False

        host = str(parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and (
                host == "dataspace.copernicus.eu"
                or host.endswith(".dataspace.copernicus.eu")
            )
        )

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
