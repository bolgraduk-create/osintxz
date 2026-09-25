from __future__ import annotations

from datetime import date

from PySide6.QtCore import QObject, Signal, Slot

from app.geo_intelligence.providers.copernicus_sentinel2 import (
    CopernicusSentinel2CatalogProvider,
    Sentinel2SceneSearchRequest,
)


class SatelliteSceneSearchWorker(QObject):
    """Run bounded Copernicus scene discovery away from the QML thread."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        target_date: str,
        window_days: int,
        max_cloud_cover: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.target_date = str(target_date or "").strip()
        self.window_days = int(window_days)
        self.max_cloud_cover = int(max_cloud_cover)

    @Slot()
    def run(self) -> None:
        try:
            parsed_date = (
                date.fromisoformat(self.target_date)
                if self.target_date
                else None
            )
            request = Sentinel2SceneSearchRequest(
                latitude=self.latitude,
                longitude=self.longitude,
                target_date=parsed_date,
                window_days=self.window_days,
                max_cloud_cover=self.max_cloud_cover,
            )
            result = CopernicusSentinel2CatalogProvider().search(request)
        except Exception as exc:
            self.failed.emit(
                {
                    "error": str(exc),
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "targetDate": self.target_date,
                    "windowDays": self.window_days,
                    "maxCloudCover": self.max_cloud_cover,
                }
            )
            return

        self.succeeded.emit(result)
