from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.interface.desktop.workers.unified_investigation_search_worker import (
    UnifiedInvestigationSearchWorker,
)


LOGGER = logging.getLogger(__name__)


class InvestigationSearchBridge(QObject):
    """QML bridge for R13.20 structured all-source investigation search."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: UnifiedInvestigationSearchWorker | None = None
        self._context: dict[str, Any] = {}

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Slot("QVariantMap", str, "QVariantMap", result=bool)
    def search(self, profile: object, case_id: str, options: object = None) -> bool:
        if self._busy:
            self._set_message("An investigation search is already running.")
            return False

        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            self._set_message("Select an investigation before running all-source search.")
            return False

        payload = dict(profile) if isinstance(profile, dict) else {}
        settings = dict(options) if isinstance(options, dict) else {}
        if not self._has_input(payload):
            self._set_message("Enter at least one known data point before searching.")
            return False

        started_at = datetime.now()
        self._context = {
            "caseId": normalized_case_id,
            "startedAt": started_at,
            "profile": payload,
            "options": settings,
        }
        self._run = {
            "hasRun": True,
            "status": "running",
            "phase": "planning",
            "progressText": "Building search plan…",
            "results": [],
            "providers": [],
            "pivots": [],
            "errors": [],
            "seeds": [],
            "summary": {
                "seeds": 0,
                "results": 0,
                "providers": 0,
                "pivots": 0,
                "errors": 0,
                "guarded": 0,
                "evidenceCreated": 0,
                "entitiesCreated": 0,
            },
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "durationText": "Running…",
            "error": "",
            "rawSecretValuesStored": False,
        }
        self._busy = True
        self._set_message("Unified investigation search started.")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = UnifiedInvestigationSearchWorker(
                case_id=normalized_case_id,
                profile=payload,
                options=settings,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._on_progress)
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
            LOGGER.exception("Unable to start unified investigation worker")
            self._busy = False
            self._thread = None
            self._worker = None
            self._context = {}
            self._run.update(
                {
                    "status": "failed",
                    "error": str(exc),
                    "durationText": "0.0s",
                }
            )
            self._set_message(f"Unable to start investigation search: {exc}")
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
    def _on_progress(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        current = dict(self._run)
        if not current:
            return
        current["phase"] = str(payload.get("phase") or "running")
        current["progressText"] = str(payload.get("detail") or "Searching…")
        summary = dict(current.get("summary") or {})
        for source_key, target_key in (
            ("seeds", "seeds"),
            ("pivots", "pivots"),
            ("providers", "providers"),
        ):
            if source_key in payload:
                summary[target_key] = int(payload.get(source_key) or 0)
        if "targetsProcessed" in payload:
            summary["targetsProcessed"] = int(payload.get("targetsProcessed") or 0)
        if "queuedTargets" in payload:
            summary["queuedTargets"] = int(payload.get("queuedTargets") or 0)
        current["summary"] = summary
        self._run = current
        self._set_message(str(payload.get("detail") or "Unified search running…"))
        self.changed.emit()

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        started_at = self._context.get("startedAt")
        run = dict(snapshot)
        run.update(
            {
                "hasRun": True,
                "phase": "completed",
                "progressText": "All selected source layers completed.",
                "startedLabel": (
                    started_at.strftime("%b %d, %Y · %H:%M:%S")
                    if isinstance(started_at, datetime)
                    else ""
                ),
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": "",
                "rawSecretValuesStored": False,
            }
        )
        self._run = run
        summary = dict(run.get("summary") or {})
        self._set_message(
            "Investigation search completed: "
            f"{int(summary.get('results') or 0)} result(s), "
            f"{int(summary.get('pivots') or 0)} new exact pivot(s), "
            f"{int(summary.get('evidenceCreated') or 0)} evidence item(s) persisted."
        )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Unknown investigation search error")
        duration = self._safe_float(payload.get("duration"))
        self._run.update(
            {
                "hasRun": True,
                "status": "failed",
                "phase": "failed",
                "progressText": error,
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": error,
                "rawSecretValuesStored": False,
            }
        )
        self._set_message(f"Investigation search failed: {error}")
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self._context = {}
        self.changed.emit()

    @staticmethod
    def _has_input(payload: dict[str, Any]) -> bool:
        ignored = {"notes", "birthDate", "country", "region", "city", "postalCode"}
        for key, value in payload.items():
            if key in ignored:
                continue
            if isinstance(value, (list, tuple, set, frozenset)):
                if any(str(item or "").strip() for item in value):
                    return True
            elif str(value or "").strip():
                return True
        # Address plus location is also a valid seed.
        return bool(str(payload.get("address") or "").strip())

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
