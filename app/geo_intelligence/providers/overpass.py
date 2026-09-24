from __future__ import annotations

import json
from typing import Any

import httpx

from app.geo_intelligence.contracts import (
    GeoEnrichmentRequest,
    GeoProviderResult,
    GeoProviderStatus,
)
from app.geo_intelligence.provider import GeoIntelligenceProvider


class OverpassNearbyProvider(GeoIntelligenceProvider):
    """Bounded nearby-POI discovery through the public Overpass API."""

    API = "https://overpass-api.de/api/interpreter"
    MAX_BYTES = 4_000_000
    TAG_KEYS = (
        "amenity",
        "shop",
        "tourism",
        "leisure",
        "office",
        "public_transport",
        "railway",
        "aeroway",
        "historic",
        "emergency",
        "healthcare",
    )

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        endpoint: str | None = None,
        user_agent: str = "OSINTXZ/1.0 GEO Overpass",
    ) -> None:
        self.transport = transport
        self.endpoint = str(endpoint or self.API).strip()
        self.user_agent = user_agent

    @property
    def source_code(self) -> str:
        return "overpass_osm"

    def enrich(self, request: GeoEnrichmentRequest) -> GeoProviderResult:
        query = self._build_query(request)

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
                response = client.post(
                    self.endpoint,
                    data={"data": query},
                )
                if len(response.content) > self.MAX_BYTES:
                    return GeoProviderResult(
                        source=self.source_code,
                        status=GeoProviderStatus.PARTIAL,
                        error="Overpass response exceeded the bounded response size.",
                        metadata={
                            "retryable": True,
                            "max_bytes": self.MAX_BYTES,
                        },
                    )
                response.raise_for_status()
                payload = json.loads(response.content)

        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            return GeoProviderResult(
                source=self.source_code,
                status=(
                    GeoProviderStatus.PARTIAL
                    if code == 429 or code >= 500
                    else GeoProviderStatus.FAILED
                ),
                error=f"Overpass HTTP {code}.",
                metadata={
                    "retryable": code == 429 or code >= 500,
                    "rate_limited": code == 429,
                },
            )
        except (httpx.RequestError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return GeoProviderResult(
                source=self.source_code,
                status=GeoProviderStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )

        rows = payload.get("elements", []) if isinstance(payload, dict) else []
        records: list[dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            coordinates = self._coordinates(row)
            if coordinates is None:
                continue

            osm_type = str(row.get("type") or "").strip().lower()
            osm_id = str(row.get("id") or "").strip()
            if not osm_type or not osm_id:
                continue

            tags = row.get("tags")
            if not isinstance(tags, dict):
                tags = {}

            category_key, category_value = self._category(tags)
            name = str(
                tags.get("name")
                or tags.get("brand")
                or tags.get("operator")
                or tags.get("ref")
                or f"{category_value or 'OSM object'} {osm_id}"
            ).strip()

            source_url = (
                f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
                if osm_type in {"node", "way", "relation"}
                else ""
            )

            records.append(
                {
                    "id": f"osm:{osm_type}:{osm_id}",
                    "kind": "poi",
                    "title": name,
                    "detail": self._detail(tags, category_key, category_value),
                    "category": category_value or category_key or "poi",
                    "categoryKey": category_key,
                    "latitude": coordinates[0],
                    "longitude": coordinates[1],
                    "source": "OpenStreetMap / Overpass",
                    "sourceUrl": source_url,
                    "osmType": osm_type,
                    "osmId": osm_id,
                    "tags": self._bounded_tags(tags),
                    "transient": True,
                }
            )

            if len(records) >= request.poi_limit:
                break

        return GeoProviderResult(
            source=self.source_code,
            status=GeoProviderStatus.SUCCESS,
            records=records,
            summary={
                "records": len(records),
                "radius_m": request.radius_m,
            },
            metadata={
                "endpoint": self.endpoint,
                "query_type": "nearby_poi",
                "read_only": True,
                "response_elements": len(rows),
                "bounded_limit": request.poi_limit,
            },
        )

    def _build_query(self, request: GeoEnrichmentRequest) -> str:
        lat = f"{request.point.latitude:.7f}"
        lon = f"{request.point.longitude:.7f}"
        radius = request.radius_m
        clauses = "\n".join(
            f'  nwr(around:{radius},{lat},{lon})["{key}"];'
            for key in self.TAG_KEYS
        )
        server_limit = min(
            max(request.poi_limit * 4, 100),
            400,
        )
        return (
            f"[out:json][timeout:{min(request.timeout_seconds, 25)}];\n"
            "(\n"
            f"{clauses}\n"
            ");\n"
            f"out center qt {server_limit};"
        )

    @staticmethod
    def _coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
        lat = row.get("lat")
        lon = row.get("lon")

        if lat is None or lon is None:
            center = row.get("center")
            if isinstance(center, dict):
                lat = center.get("lat")
                lon = center.get("lon")

        try:
            latitude = float(lat)
            longitude = float(lon)
        except (TypeError, ValueError):
            return None

        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return None
        return latitude, longitude

    @classmethod
    def _category(cls, tags: dict[str, Any]) -> tuple[str, str]:
        for key in cls.TAG_KEYS:
            value = str(tags.get(key) or "").strip()
            if value:
                return key, value
        return "", ""

    @staticmethod
    def _detail(
        tags: dict[str, Any],
        category_key: str,
        category_value: str,
    ) -> str:
        parts: list[str] = []
        if category_value:
            parts.append(category_value.replace("_", " ").title())

        address = " ".join(
            str(tags.get(key) or "").strip()
            for key in ("addr:housenumber", "addr:street")
            if str(tags.get(key) or "").strip()
        )
        if address:
            parts.append(address)

        phone = str(tags.get("contact:phone") or tags.get("phone") or "").strip()
        website = str(tags.get("contact:website") or tags.get("website") or "").strip()
        if phone:
            parts.append(phone)
        if website:
            parts.append(website)

        if not parts and category_key:
            parts.append(category_key.replace("_", " ").title())

        return " · ".join(parts)[:500]

    @staticmethod
    def _bounded_tags(tags: dict[str, Any]) -> dict[str, str]:
        allowed = {
            "name",
            "brand",
            "operator",
            "amenity",
            "shop",
            "tourism",
            "leisure",
            "office",
            "public_transport",
            "railway",
            "aeroway",
            "historic",
            "emergency",
            "healthcare",
            "addr:housenumber",
            "addr:street",
            "addr:city",
            "contact:phone",
            "phone",
            "contact:website",
            "website",
            "opening_hours",
            "wikidata",
            "wikipedia",
        }
        result: dict[str, str] = {}
        for key, value in tags.items():
            if str(key) not in allowed:
                continue
            text = str(value or "").strip()
            if text:
                result[str(key)] = text[:500]
        return result
