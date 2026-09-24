from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.geo_intelligence.contracts import GeoEnrichmentRequest, GeoPoint
from app.geo_intelligence.service import GeoIntelligenceService
from app.interface.desktop.workers.geo_enrichment_worker import (
    GeoEnrichmentWorker,
)


class GeoBridge(QObject):
    """Transient QML bridge for live, read-only GEO enrichment."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: GeoEnrichmentWorker | None = None

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Slot(float, float, str, int, result=bool)
    def runEnrichment(
        self,
        latitude: float,
        longitude: float,
        historical_date: str,
        radius_m: int,
    ) -> bool:
        if self._busy:
            self._set_message("GEO enrichment is already running.")
            return False

        normalized_date = str(historical_date or "").strip()

        try:
            request = GeoEnrichmentRequest(
                point=GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude),
                ),
                radius_m=int(radius_m),
                historical_date=GeoIntelligenceService._parse_date(
                    normalized_date
                ),
            )
        except (TypeError, ValueError) as exc:
            self._set_message(str(exc))
            return False

        self._run = {
            "hasRun": True,
            "status": "running",
            "latitude": request.point.latitude,
            "longitude": request.point.longitude,
            "historicalDate": normalized_date,
            "radiusMeters": request.radius_m,
            "nearbyPlaces": [],
            "weather": {
                "available": False,
                "summary": {},
                "hourly": [],
            },
            "providers": [],
            "summary": {
                "nearbyPlaces": 0,
                "weatherAvailable": False,
                "providerFailures": 0,
                "providerPartials": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._busy = True
        self._set_message("Running live GEO enrichment…")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = GeoEnrichmentWorker(
                latitude=request.point.latitude,
                longitude=request.point.longitude,
                historical_date=normalized_date,
                radius_m=request.radius_m,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_succeeded)
            worker.failed.connect(self._on_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._thread = thread
            self._worker = worker
            thread.start()
            return True
        except Exception as exc:
            self._busy = False
            self._thread = None
            self._worker = None
            self._run.update(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            )
            self._set_message(
                "Unable to start GEO enrichment: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot()
    def clear(self) -> None:
        if self._busy:
            return
        self._run = {}
        self._set_message("")
        self.changed.emit()

    @Slot(object)
    def _on_succeeded(self, payload: object) -> None:
        self._busy = False
        self._run = (
            dict(payload)
            if isinstance(payload, dict)
            else {
                "hasRun": True,
                "status": "failed",
                "error": "GEO provider returned an invalid result.",
            }
        )

        status = str(self._run.get("status") or "")
        summary = self._run.get("summary")
        if not isinstance(summary, dict):
            summary = {}

        if status == "failed":
            self._set_message("GEO enrichment failed.")
        else:
            self._set_message(
                "GEO enrichment complete: "
                + str(int(summary.get("nearbyPlaces") or 0))
                + " nearby place(s)."
            )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, payload: object) -> None:
        self._busy = False
        data = dict(payload) if isinstance(payload, dict) else {}
        error = str(data.get("error") or "Unknown GEO enrichment failure.")
        self._run = {
            "hasRun": True,
            "status": "failed",
            "error": error,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "historicalDate": data.get("historicalDate") or "",
            "radiusMeters": data.get("radiusMeters") or 0,
            "nearbyPlaces": [],
            "weather": {
                "available": False,
                "summary": {},
                "hourly": [],
            },
            "providers": [],
            "summary": {
                "nearbyPlaces": 0,
                "weatherAvailable": False,
                "providerFailures": 1,
                "providerPartials": 0,
            },
            "transient": True,
            "persisted": False,
        }
        self._set_message("GEO enrichment failed: " + error)
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._thread = None
        self._worker = None
        self.changed.emit()

    def _set_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._message:
            return
        self._message = normalized
        self.messageChanged.emit()
