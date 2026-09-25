from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import CACHE_DIR


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


@dataclass(frozen=True, slots=True)
class Sentinel2RenderRequest:
    scene: dict[str, Any]
    latitude: float
    longitude: float
    radius_m: int = 3_000
    size_px: int = 768
    timeout_seconds: int = 45

    def __post_init__(self) -> None:
        latitude = float(self.latitude)
        longitude = float(self.longitude)
        radius_m = int(self.radius_m)
        size_px = int(self.size_px)
        timeout_seconds = int(self.timeout_seconds)

        if not -90.0 <= latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90.")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("longitude must be between -180 and 180.")
        if not 500 <= radius_m <= 20_000:
            raise ValueError("radius_m must be 500..20000.")
        if not 256 <= size_px <= 1_024:
            raise ValueError("size_px must be 256..1024.")
        if not 10 <= timeout_seconds <= 90:
            raise ValueError("timeout_seconds must be 10..90.")

        acquired_at = str((self.scene or {}).get("acquiredAt") or "").strip()
        if len(acquired_at) < 10:
            raise ValueError("Selected Sentinel-2 scene has no acquisition date.")
        try:
            date.fromisoformat(acquired_at[:10])
        except ValueError as exc:
            raise ValueError("Selected Sentinel-2 scene has an invalid acquisition date.") from exc

        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)
        object.__setattr__(self, "radius_m", radius_m)
        object.__setattr__(self, "size_px", size_px)
        object.__setattr__(self, "timeout_seconds", timeout_seconds)


class CopernicusSentinel2CatalogProvider:
    """No-auth Sentinel-2 L2A discovery through the official CDSE STAC API."""

    API = "https://stac.dataspace.copernicus.eu/v1/search"
    COLLECTION = "sentinel-2-l2a"
    MAX_BYTES = 3_000_000

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        endpoint: str | None = None,
        user_agent: str = "OSINTXZ/0.1 GEO Copernicus STAC",
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
        body = {
            "collections": [self.COLLECTION],
            "intersects": {
                "type": "Point",
                "coordinates": [
                    request.longitude,
                    request.latitude,
                ],
            },
            "datetime": (
                f"{start_date.isoformat()}T00:00:00Z/"
                f"{end_date.isoformat()}T23:59:59Z"
            ),
            "query": {
                "eo:cloud_cover": {
                    "lte": request.max_cloud_cover,
                }
            },
            "sortby": [
                {
                    "field": "properties.datetime",
                    "direction": "desc",
                }
            ],
            "limit": min(max(request.limit * 2, 12), 24),
        }

        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(request.timeout_seconds)),
                transport=self.transport,
                follow_redirects=False,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/geo+json, application/json",
                },
            ) as client:
                response = client.post(
                    self.endpoint,
                    json=body,
                )
                if len(response.content) > self.MAX_BYTES:
                    return {
                        "status": "partial",
                        "error": "Copernicus STAC response exceeded the bounded response size.",
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
                "error": f"Copernicus STAC HTTP {code}.",
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

        rows = payload.get("features", []) if isinstance(payload, dict) else []
        scenes: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            scene = self._scene(row)
            if scene:
                scenes.append(scene)

        if request.target_date is not None:
            scenes.sort(
                key=lambda scene: self._scene_rank(
                    scene,
                    request.target_date,
                )
            )

        scenes = scenes[: request.limit]

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
    def _scene_rank(
        scene: dict[str, Any],
        target_date: date,
    ) -> tuple[int, float, str]:
        acquired = str(scene.get("acquiredAt") or "")
        try:
            acquired_date = date.fromisoformat(acquired[:10])
            distance = abs((acquired_date - target_date).days)
        except ValueError:
            distance = 10_000

        cloud = scene.get("cloudCover")
        try:
            cloud_value = float(cloud)
        except (TypeError, ValueError):
            cloud_value = 101.0

        return distance, cloud_value, acquired

    @staticmethod
    def _date_window(
        request: Sentinel2SceneSearchRequest,
    ) -> tuple[date, date]:
        if request.target_date is not None:
            return (
                request.target_date - timedelta(days=request.window_days),
                min(
                    request.target_date + timedelta(days=request.window_days),
                    date.today(),
                ),
            )

        end = date.today()
        return end - timedelta(days=30), end

    @classmethod
    def _scene(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        scene_id = str(row.get("id") or "").strip()
        if not scene_id:
            return None

        properties = row.get("properties")
        if not isinstance(properties, dict):
            properties = {}

        assets = row.get("assets")
        if not isinstance(assets, dict):
            assets = {}

        links = row.get("links")
        if not isinstance(links, list):
            links = []

        bbox = row.get("bbox")
        if not (
            isinstance(bbox, list)
            and len(bbox) >= 4
        ):
            bbox = cls._footprint_bbox(row.get("geometry"))
        else:
            bbox = [
                cls._float_or_none(value)
                for value in bbox[:4]
            ]
            if any(value is None for value in bbox):
                bbox = []

        quicklook = cls._quicklook(assets)

        source_url = ""
        for link in links:
            if not isinstance(link, dict):
                continue
            if str(link.get("rel") or "").strip().lower() == "self":
                candidate = str(link.get("href") or "").strip()
                if cls._safe_metadata_url(candidate):
                    source_url = candidate
                    break
        if not source_url:
            source_url = (
                "https://stac.dataspace.copernicus.eu/v1/collections/"
                f"{cls.COLLECTION}/items/{scene_id}"
            )

        acquired_at = str(
            properties.get("datetime")
            or properties.get("start_datetime")
            or ""
        )

        return {
            "id": scene_id,
            "name": scene_id,
            "mission": "Sentinel-2",
            "platform": str(properties.get("platform") or ""),
            "productType": "S2MSI2A",
            "acquiredAt": acquired_at,
            "endedAt": str(properties.get("end_datetime") or acquired_at),
            "cloudCover": cls._float_or_none(properties.get("eo:cloud_cover")),
            "online": True,
            "contentLength": None,
            "s3Path": "",
            "footprint": row.get("geometry") if isinstance(row.get("geometry"), dict) else {},
            "bbox": bbox,
            "quicklookUrl": quicklook,
            "source": "Copernicus Data Space Ecosystem",
            "sourceUrl": source_url,
            "catalog": "STAC 1.1",
            "transient": True,
        }

    @classmethod
    def _quicklook(
        cls,
        assets: dict[str, Any],
    ) -> str:
        candidates: list[tuple[int, str]] = []
        for key, raw in assets.items():
            if not isinstance(raw, dict):
                continue
            href = str(raw.get("href") or "").strip()
            if not href or not cls._safe_asset_url(href):
                continue

            roles = raw.get("roles")
            role_values = (
                [str(item).lower() for item in roles]
                if isinstance(roles, list)
                else []
            )
            media_type = str(raw.get("type") or "").lower()
            probe = (str(key) + " " + str(raw.get("title") or "")).lower()

            score = 0
            if "thumbnail" in role_values:
                score += 100
            if "overview" in role_values:
                score += 90
            if "thumbnail" in probe or "quicklook" in probe:
                score += 80
            if media_type in {"image/jpeg", "image/png", "image/webp"}:
                score += 30
            if score:
                candidates.append((score, href))

        if not candidates:
            return ""
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _footprint_bbox(value: Any) -> list[float]:
        if not isinstance(value, dict):
            return []

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

        walk(value.get("coordinates"))
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
    def _safe_metadata_url(value: str) -> bool:
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
    def _safe_asset_url(value: str) -> bool:
        return CopernicusSentinel2CatalogProvider._safe_metadata_url(value)


class CopernicusSentinel2Renderer:
    """Optional-auth bounded True Color rendering through CDSE Sentinel Hub."""

    TOKEN_URL = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
        "protocol/openid-connect/token"
    )
    PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"
    MAX_IMAGE_BYTES = 12_000_000
    EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04", "dataMask"],
    output: { bands: 4, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  return [
    2.5 * sample.B04,
    2.5 * sample.B03,
    2.5 * sample.B02,
    sample.dataMask
  ];
}
"""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_transport: httpx.BaseTransport | None = None,
        process_transport: httpx.BaseTransport | None = None,
        cache_dir: Path | None = None,
        user_agent: str = "OSINTXZ/0.1 GEO SentinelHub",
    ) -> None:
        self.client_id = str(client_id or "").strip()
        self.client_secret = str(client_secret or "").strip()
        self.token_transport = token_transport
        self.process_transport = process_transport
        self.cache_dir = Path(cache_dir or (CACHE_DIR / "satellite"))
        self.user_agent = user_agent

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def render(
        self,
        request: Sentinel2RenderRequest,
    ) -> dict[str, Any]:
        if not self.configured:
            return {
                "status": "skipped",
                "error": "Copernicus OAuth client is not configured.",
                "configured": False,
            }

        token = self._token(request.timeout_seconds)
        if not token:
            return {
                "status": "failed",
                "error": "Unable to obtain Copernicus OAuth access token.",
                "configured": True,
            }

        bbox = self._bbox(
            request.latitude,
            request.longitude,
            request.radius_m,
        )
        acquired_date = date.fromisoformat(
            str(request.scene.get("acquiredAt") or "")[:10]
        )
        day = acquired_date.isoformat()

        cloud_value = request.scene.get("cloudCover")
        try:
            max_cloud = min(100, max(5, int(math.ceil(float(cloud_value))) + 5))
        except (TypeError, ValueError):
            max_cloud = 100

        payload = {
            "input": {
                "bounds": {
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    },
                    "bbox": bbox,
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {
                                "from": f"{day}T00:00:00Z",
                                "to": f"{day}T23:59:59Z",
                            },
                            "maxCloudCoverage": max_cloud,
                            "mosaickingOrder": "leastCC",
                        },
                    }
                ],
            },
            "output": {
                "width": request.size_px,
                "height": request.size_px,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {
                            "type": "image/png",
                        },
                    }
                ],
            },
            "evalscript": self.EVALSCRIPT,
        }

        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(request.timeout_seconds)),
                transport=self.process_transport,
                follow_redirects=False,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "image/png",
                    "Authorization": f"Bearer {token}",
                },
            ) as client:
                response = client.post(
                    self.PROCESS_URL,
                    json=payload,
                )
                response.raise_for_status()

                content_type = str(response.headers.get("content-type") or "").lower()
                if "image/png" not in content_type:
                    return {
                        "status": "failed",
                        "error": "Copernicus Process API did not return PNG imagery.",
                        "configured": True,
                    }
                if not response.content:
                    return {
                        "status": "failed",
                        "error": "Copernicus Process API returned an empty image.",
                        "configured": True,
                    }
                if len(response.content) > self.MAX_IMAGE_BYTES:
                    return {
                        "status": "failed",
                        "error": "Copernicus rendered image exceeded the bounded size.",
                        "configured": True,
                    }
                image_bytes = bytes(response.content)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            return {
                "status": "partial" if code == 429 or code >= 500 else "failed",
                "error": f"Copernicus Process API HTTP {code}.",
                "configured": True,
                "retryable": code == 429 or code >= 500,
                "rateLimited": code == 429,
            }
        except httpx.RequestError as exc:
            return {
                "status": "partial",
                "error": str(exc),
                "configured": True,
                "retryable": True,
            }

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        output_path = (self.cache_dir / "sentinel2_true_color_current.png").resolve()
        temporary = output_path.with_suffix(".tmp")
        temporary.write_bytes(image_bytes)
        temporary.replace(output_path)

        return {
            "status": "completed",
            "error": "",
            "configured": True,
            "sceneId": str(request.scene.get("id") or ""),
            "acquiredAt": str(request.scene.get("acquiredAt") or ""),
            "renderPath": str(output_path),
            "renderBbox": bbox,
            "renderMode": "true_color",
            "imageBytes": len(image_bytes),
            "transient": True,
            "persisted": False,
        }

    def _token(
        self,
        timeout_seconds: int,
    ) -> str:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(timeout_seconds)),
                transport=self.token_transport,
                follow_redirects=False,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as client:
                response = client.post(
                    self.TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return ""

        if not isinstance(payload, dict):
            return ""
        return str(payload.get("access_token") or "").strip()

    @staticmethod
    def _bbox(
        latitude: float,
        longitude: float,
        radius_m: int,
    ) -> list[float]:
        lat_delta = radius_m / 111_320.0
        lon_scale = max(0.05, math.cos(math.radians(latitude)))
        lon_delta = radius_m / (111_320.0 * lon_scale)

        return [
            max(-180.0, longitude - lon_delta),
            max(-85.05112878, latitude - lat_delta),
            min(180.0, longitude + lon_delta),
            min(85.05112878, latitude + lat_delta),
        ]
