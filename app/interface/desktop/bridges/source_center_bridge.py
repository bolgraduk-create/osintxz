from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.intelligence_sources.source_center import build_source_center_snapshot
from app.interface.desktop.workers.federated_source_search_worker import (
    FederatedSourceSearchWorker,
)

LOGGER = logging.getLogger(__name__)


class SourceCenterBridge(QObject):
    """Presentation bridge for source inventory and bounded Federation search."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._center: dict[str, Any] = {}
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: FederatedSourceSearchWorker | None = None
        self._context: dict[str, Any] = {}
        self.refresh()

    @Property("QVariantMap", notify=changed)
    def sourceCenter(self) -> dict[str, Any]:
        return dict(self._center)

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Slot()
    def refresh(self) -> None:
        try:
            self._center = build_source_center_snapshot(self._container)
            counts = dict(self._center.get("counts") or {})
            self._set_message(
                f"{int(counts.get('total') or 0)} sources known; "
                f"{int(counts.get('searchable') or 0)} Federation adapters searchable here."
            )
        except Exception as exc:
            LOGGER.exception("Unable to build source center snapshot")
            self._center = {"sources": [], "capabilityCodes": [], "capabilityLabels": [], "counts": {}}
            self._set_message(f"Unable to load source catalog: {exc}")
        self.changed.emit()

    @Slot(str, str, str, str, bool, result=bool)
    def search(
        self,
        capability: str,
        value: str,
        country: str = "",
        source_code: str = "",
        verified_scope: bool = False,
    ) -> bool:
        if self._busy:
            self._set_message("A Federation search is already running.")
            return False

        normalized_capability = str(capability or "").strip().casefold()
        normalized_value = str(value or "").strip()
        normalized_country = str(country or "").strip().upper()
        normalized_source = str(source_code or "").strip().casefold()
        if not normalized_capability or not normalized_value:
            self._set_message("Choose a capability and enter a target value.")
            return False
        if normalized_country and (len(normalized_country) != 2 or not normalized_country.isalpha()):
            self._set_message("Country must be a two-letter ISO code or blank.")
            return False

        if normalized_source:
            source = next(
                (
                    item for item in list(self._center.get("sources") or [])
                    if str(item.get("code") or "").casefold() == normalized_source
                    and bool(item.get("searchable"))
                ),
                None,
            )
            if source is None:
                self._set_message("The selected source is not a Federation adapter.")
                return False
            if normalized_capability not in set(source.get("capabilities") or []):
                self._set_message("The selected source does not support this capability.")
                return False
            if bool(source.get("requiresVerifiedScope")) and not verified_scope:
                self._set_message("This source requires confirmed verified scope.")
                return False

        started_at = datetime.now()
        self._context = {
            "capability": normalized_capability,
            "value": normalized_value,
            "country": normalized_country,
            "sourceCode": normalized_source,
            "verifiedScope": bool(verified_scope),
            "startedAt": started_at,
        }
        self._run = {
            "hasRun": True,
            "status": "running",
            "capability": normalized_capability,
            "value": normalized_value,
            "country": normalized_country,
            "sourceCode": normalized_source,
            "verifiedScope": bool(verified_scope),
            "records": [],
            "providers": [],
            "summary": {"records": 0, "providers": 0, "successful": 0, "partial": 0, "notConfigured": 0, "failed": 0, "notSupported": 0},
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "durationText": "Running…",
            "error": "",
            "rawSecretValuesStored": False,
        }
        self._busy = True
        self._set_message(f"Federated search running for {normalized_value}.")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = FederatedSourceSearchWorker(
                capability=normalized_capability,
                value=normalized_value,
                country=normalized_country,
                source_code=normalized_source,
                verified_scope=bool(verified_scope),
                limit=20,
                timeout=30,
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
            LOGGER.exception("Unable to start Federation search worker")
            self._busy = False
            self._thread = None
            self._worker = None
            self._context = {}
            self._run.update({"status": "failed", "error": str(exc), "durationText": "0.0s"})
            self._set_message(f"Unable to start Federation search: {exc}")
            self.changed.emit()
            return False

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        started_at = self._context.get("startedAt")
        run = dict(snapshot)
        run.update({
            "hasRun": True,
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S") if isinstance(started_at, datetime) else "",
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "sourceCode": str(self._context.get("sourceCode") or ""),
            "error": "",
            "rawSecretValuesStored": False,
        })
        self._run = run
        summary = dict(run.get("summary") or {})
        self._set_message(
            f"Federated search completed: {int(summary.get('records') or 0)} record(s) "
            f"from {int(summary.get('providers') or 0)} provider execution(s)."
        )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        duration = self._safe_float(payload.get("duration"))
        error = str(payload.get("error") or "Unknown Federation error")
        self._run.update({
            "hasRun": True,
            "status": "failed",
            "error": error,
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "records": [],
            "providers": [],
            "rawSecretValuesStored": False,
        })
        self._set_message(f"Federated search failed: {error}")
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self._context = {}
        self.changed.emit()

    def _set_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized != self._message:
            self._message = normalized
            self.messageChanged.emit()

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
