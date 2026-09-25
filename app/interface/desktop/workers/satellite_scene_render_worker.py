from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.core.config import settings
from app.geo_intelligence.providers.copernicus_sentinel2 import (
    CopernicusSentinel2Renderer,
    Sentinel2RenderRequest,
)


class SatelliteSceneRenderWorker(QObject):
    """Render one bounded Sentinel-2 True Color image off the QML thread."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        scene: dict,
        latitude: float,
        longitude: float,
        radius_m: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.scene = dict(scene or {})
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.radius_m = int(radius_m)

    @Slot()
    def run(self) -> None:
        try:
            client_id = str(settings.cdse_client_id or "").strip()
            client_secret = (
                settings.cdse_client_secret.get_secret_value().strip()
                if settings.cdse_client_secret is not None
                else ""
            )

            renderer = CopernicusSentinel2Renderer(
                client_id=client_id,
                client_secret=client_secret,
            )
            result = renderer.render(
                Sentinel2RenderRequest(
                    scene=self.scene,
                    latitude=self.latitude,
                    longitude=self.longitude,
                    radius_m=self.radius_m,
                )
            )
        except Exception as exc:
            self.failed.emit(
                {
                    "error": str(exc),
                    "sceneId": str(self.scene.get("id") or ""),
                }
            )
            return

        if str(result.get("status") or "") == "failed":
            self.failed.emit(result)
            return

        self.succeeded.emit(result)
