from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.geo_intelligence.service import GeoIntelligenceService


class GeoEnrichmentWorker(QObject):
    """Run bounded network GEO enrichment away from the QML thread."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        historical_date: str,
        radius_m: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.historical_date = str(historical_date or "").strip()
        self.radius_m = int(radius_m)

    @Slot()
    def run(self) -> None:
        try:
            result = GeoIntelligenceService().enrich(
                latitude=self.latitude,
                longitude=self.longitude,
                radius_m=self.radius_m,
                historical_date=self.historical_date,
            )
        except Exception as exc:
            self.failed.emit(
                {
                    "error": str(exc),
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "historicalDate": self.historical_date,
                    "radiusMeters": self.radius_m,
                }
            )
            return

        self.succeeded.emit(result)
