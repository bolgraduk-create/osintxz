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


class OpenMeteoHistoricalProvider(GeoIntelligenceProvider):
    """Historical weather context for a coordinate and a specific date."""

    API = "https://archive-api.open-meteo.com/v1/archive"
    MAX_BYTES = 1_500_000
    HOURLY = (
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "snowfall",
        "weather_code",
        "cloud_cover",
        "visibility",
        "wind_speed_10m",
        "wind_direction_10m",
    )
    DAILY = (
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "snowfall_sum",
        "sunrise",
        "sunset",
    )

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        endpoint: str | None = None,
        user_agent: str = "OSINTXZ/1.0 GEO OpenMeteo",
    ) -> None:
        self.transport = transport
        self.endpoint = str(endpoint or self.API).strip()
        self.user_agent = user_agent

    @property
    def source_code(self) -> str:
        return "open_meteo_historical"

    def enrich(self, request: GeoEnrichmentRequest) -> GeoProviderResult:
        if request.historical_date is None:
            return GeoProviderResult(
                source=self.source_code,
                status=GeoProviderStatus.SKIPPED,
                metadata={"reason": "historical_date_not_requested"},
            )

        day = request.historical_date.isoformat()

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
                        "latitude": request.point.latitude,
                        "longitude": request.point.longitude,
                        "start_date": day,
                        "end_date": day,
                        "hourly": ",".join(self.HOURLY),
                        "daily": ",".join(self.DAILY),
                        "timezone": "UTC",
                    },
                )
                if len(response.content) > self.MAX_BYTES:
                    return GeoProviderResult(
                        source=self.source_code,
                        status=GeoProviderStatus.PARTIAL,
                        error="Open-Meteo response exceeded the bounded response size.",
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
                error=f"Open-Meteo HTTP {code}.",
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

        if not isinstance(payload, dict):
            return GeoProviderResult(
                source=self.source_code,
                status=GeoProviderStatus.FAILED,
                error="Open-Meteo returned an invalid payload.",
            )

        summary = self._daily_summary(payload, day)
        hourly = self._hourly_rows(payload)

        return GeoProviderResult(
            source=self.source_code,
            status=GeoProviderStatus.SUCCESS,
            records=hourly,
            summary=summary,
            metadata={
                "endpoint": self.endpoint,
                "timezone": str(payload.get("timezone") or "UTC"),
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "elevation": payload.get("elevation"),
                "read_only": True,
                "historical_date": day,
            },
        )

    @classmethod
    def _hourly_rows(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            return []

        times = hourly.get("time")
        if not isinstance(times, list):
            return []

        rows: list[dict[str, Any]] = []
        for index, timestamp in enumerate(times[:24]):
            row: dict[str, Any] = {
                "time": str(timestamp or ""),
            }
            for key in cls.HOURLY:
                values = hourly.get(key)
                row[key] = (
                    values[index]
                    if isinstance(values, list) and index < len(values)
                    else None
                )
            rows.append(row)
        return rows

    @classmethod
    def _daily_summary(
        cls,
        payload: dict[str, Any],
        day: str,
    ) -> dict[str, Any]:
        daily = payload.get("daily")
        if not isinstance(daily, dict):
            daily = {}

        summary: dict[str, Any] = {
            "date": day,
        }
        for key in cls.DAILY:
            values = daily.get(key)
            summary[key] = (
                values[0]
                if isinstance(values, list) and values
                else None
            )

        summary["units"] = (
            dict(payload.get("daily_units"))
            if isinstance(payload.get("daily_units"), dict)
            else {}
        )
        return summary
