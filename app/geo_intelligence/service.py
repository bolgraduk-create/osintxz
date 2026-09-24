from __future__ import annotations

from datetime import date
from typing import Any

from app.geo_intelligence.contracts import (
    GeoEnrichmentRequest,
    GeoPoint,
    GeoProviderResult,
    GeoProviderStatus,
)
from app.geo_intelligence.providers import (
    OpenMeteoHistoricalProvider,
    OverpassNearbyProvider,
)


class GeoIntelligenceService:
    """Isolated, read-only orchestration for live GEO enrichment."""

    def __init__(
        self,
        *,
        overpass: OverpassNearbyProvider | None = None,
        weather: OpenMeteoHistoricalProvider | None = None,
    ) -> None:
        self.overpass = overpass or OverpassNearbyProvider()
        self.weather = weather or OpenMeteoHistoricalProvider()

    def enrich(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 750,
        historical_date: str = "",
        poi_limit: int = 40,
        timeout_seconds: int = 20,
    ) -> dict[str, Any]:
        parsed_date = self._parse_date(historical_date)
        request = GeoEnrichmentRequest(
            point=GeoPoint(
                latitude=latitude,
                longitude=longitude,
            ),
            radius_m=radius_m,
            historical_date=parsed_date,
            poi_limit=poi_limit,
            timeout_seconds=timeout_seconds,
        )

        provider_results = [
            self._safe_call(self.overpass, request),
            self._safe_call(self.weather, request),
        ]

        overpass_result = provider_results[0]
        weather_result = provider_results[1]
        weather_available = (
            weather_result.usable
            and bool(weather_result.summary)
        )

        usable_count = sum(1 for item in provider_results if item.usable)
        failed_count = sum(
            1
            for item in provider_results
            if item.status is GeoProviderStatus.FAILED
        )
        partial_count = sum(
            1
            for item in provider_results
            if item.status is GeoProviderStatus.PARTIAL
        )

        if failed_count == len(provider_results):
            overall = "failed"
        elif failed_count or partial_count:
            overall = "partial"
        elif usable_count:
            overall = "completed"
        else:
            overall = "completed"

        return {
            "hasRun": True,
            "status": overall,
            "latitude": request.point.latitude,
            "longitude": request.point.longitude,
            "radiusMeters": request.radius_m,
            "historicalDate": (
                request.historical_date.isoformat()
                if request.historical_date is not None
                else ""
            ),
            "nearbyPlaces": [
                dict(item)
                for item in overpass_result.records
            ],
            "weather": {
                "available": weather_available,
                "summary": dict(weather_result.summary),
                "hourly": [
                    dict(item)
                    for item in weather_result.records
                ],
            },
            "providers": [
                self._provider_payload(item)
                for item in provider_results
            ],
            "summary": {
                "nearbyPlaces": len(overpass_result.records),
                "weatherAvailable": weather_available,
                "providerFailures": failed_count,
                "providerPartials": partial_count,
            },
            "transient": True,
            "persisted": False,
        }

    @staticmethod
    def _safe_call(provider: Any, request: GeoEnrichmentRequest) -> GeoProviderResult:
        try:
            return provider.enrich(request)
        except Exception as exc:
            return GeoProviderResult(
                source=str(getattr(provider, "source_code", "geo_provider")),
                status=GeoProviderStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

    @staticmethod
    def _provider_payload(result: GeoProviderResult) -> dict[str, Any]:
        return {
            "source": result.source,
            "status": result.status.value,
            "error": result.error,
            "recordCount": len(result.records),
            "metadata": dict(result.metadata),
        }

    @staticmethod
    def _parse_date(value: str) -> date | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        try:
            return date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("Historical date must use YYYY-MM-DD.") from exc
