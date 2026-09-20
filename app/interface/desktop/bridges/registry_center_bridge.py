from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.interface.desktop.workers.registry_center_worker import (
    RegistryCenterWorker,
)
from app.registry_intelligence.source_center import (
    build_registry_center_snapshot,
)


LOGGER = logging.getLogger(__name__)


class RegistryCenterBridge(QObject):
    """Presentation bridge for the provider-aware Registry Intelligence UI."""

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
        self._worker: RegistryCenterWorker | None = None
        self._context: dict[str, Any] = {}
        self.refresh()

    @Property("QVariantMap", notify=changed)
    def registryCenter(self) -> dict[str, Any]:
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
            self._center = build_registry_center_snapshot(self._container)
            counts = dict(self._center.get("counts") or {})
            self._set_message(
                f"{int(counts.get('providers') or 0)} Registry provider(s); "
                f"{int(counts.get('ready') or 0)} ready."
            )
        except Exception as exc:
            LOGGER.exception("Unable to build Registry center snapshot")
            self._center = {
                "providers": [],
                "providerCodes": [],
                "providerLabels": [],
                "domainCodes": [],
                "domainLabels": [],
                "queryKindCodes": [],
                "queryKindLabels": [],
                "countryCodes": [],
                "counts": {},
            }
            self._set_message(f"Unable to load Registry providers: {exc}")
        self.changed.emit()

    @Slot(str, str, str, str, str, result=bool)
    def search(
        self,
        domain: str,
        query_kind: str,
        value: str,
        country: str = "",
        source_code: str = "",
    ) -> bool:
        return self._start(
            domain=domain,
            query_kind=query_kind,
            value=value,
            country=country,
            source_code=source_code,
            persist=False,
            case_id="",
        )

    @Slot(str, result=bool)
    def persistLast(self, case_id: str) -> bool:
        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            self._set_message(
                "Select an investigation before saving registry intelligence."
            )
            return False

        current = dict(self._run)
        if not current or not current.get("hasRun"):
            self._set_message("Run a registry search before saving results.")
            return False
        if str(current.get("status") or "") not in {
            "completed",
            "completed_with_errors",
        }:
            self._set_message("Wait for the current registry operation to finish.")
            return False

        summary = dict(current.get("summary") or {})
        if int(summary.get("persistable") or 0) < 1:
            self._set_message(
                "Current results are candidates only or contain no persistable records."
            )
            return False

        query = dict(current.get("query") or {})
        sources = list(query.get("sources") or [])
        return self._start(
            domain=str(query.get("domain") or ""),
            query_kind=str(query.get("kind") or ""),
            value=str(current.get("value") or ""),
            country=str(query.get("country") or ""),
            source_code=str(sources[0]) if sources else "",
            persist=True,
            case_id=normalized_case_id,
        )

    def _start(
        self,
        *,
        domain: str,
        query_kind: str,
        value: str,
        country: str,
        source_code: str,
        persist: bool,
        case_id: str,
    ) -> bool:
        if self._busy:
            self._set_message("A Registry Intelligence operation is already running.")
            return False

        normalized_domain = str(domain or "").strip().casefold()
        normalized_kind = str(query_kind or "").strip().casefold()
        normalized_value = str(value or "").strip()
        normalized_country = str(country or "").strip().upper()
        normalized_source = str(source_code or "").strip().casefold()

        if not normalized_domain or not normalized_kind or not normalized_value:
            self._set_message("Choose a domain/query kind and enter a value.")
            return False
        if normalized_country and (
            len(normalized_country) != 2 or not normalized_country.isalpha()
        ):
            self._set_message("Country must be a two-letter ISO code or blank.")
            return False

        if normalized_source:
            selected = next(
                (
                    item
                    for item in list(self._center.get("providers") or [])
                    if str(item.get("code") or "").casefold() == normalized_source
                ),
                None,
            )
            if selected is None:
                self._set_message("The selected Registry provider is unavailable.")
                return False
            if normalized_domain not in set(selected.get("domains") or []):
                self._set_message("The selected provider does not support this domain.")
                return False
            if normalized_kind not in set(selected.get("queryKinds") or []):
                self._set_message("The selected provider does not support this query kind.")
                return False
            if not bool(selected.get("runnableExplicit")):
                self._set_message(
                    "The selected provider is not executable: configure credentials "
                    "or use its documented manual workflow."
                )
                return False

        started_at = datetime.now()
        previous = dict(self._run)
        self._context = {
            "domain": normalized_domain,
            "queryKind": normalized_kind,
            "value": normalized_value,
            "country": normalized_country,
            "sourceCode": normalized_source,
            "persist": bool(persist),
            "caseId": str(case_id or ""),
            "startedAt": started_at,
            "previous": previous,
        }

        if persist and previous:
            running = dict(previous)
            running.update(
                {
                    "status": "saving",
                    "operation": "save",
                    "error": "",
                    "durationText": "Saving…",
                }
            )
            self._run = running
        else:
            self._run = {
                "hasRun": True,
                "status": "running",
                "operation": "search",
                "value": normalized_value,
                "query": {
                    "domain": normalized_domain,
                    "kind": normalized_kind,
                    "country": normalized_country,
                    "sources": [normalized_source] if normalized_source else [],
                },
                "records": [],
                "providers": [],
                "route": {},
                "summary": {
                    "records": 0,
                    "persistable": 0,
                    "candidates": 0,
                    "sensitiveLegal": 0,
                    "providerExecutions": 0,
                    "providerErrors": 0,
                    "blocked": 0,
                    "missingSources": 0,
                },
                "persistence": {
                    "attempted": False,
                    "sourcesCreated": 0,
                    "evidencesCreated": 0,
                    "entitiesCreated": 0,
                    "linksCreated": 0,
                    "skippedRecords": 0,
                    "errors": [],
                    "records": [],
                },
                "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
                "durationText": "Running…",
                "error": "",
            }

        self._busy = True
        self._set_message(
            "Saving Registry Intelligence…"
            if persist
            else f"Registry search running for {normalized_value}."
        )
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = RegistryCenterWorker(
                domain=normalized_domain,
                query_kind=normalized_kind,
                value=normalized_value,
                country=normalized_country,
                source_code=normalized_source,
                persist=persist,
                case_id=str(case_id or ""),
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
            LOGGER.exception("Unable to start Registry Center worker")
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
            self._set_message(f"Unable to start Registry search: {exc}")
            self.changed.emit()
            return False

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            snapshot = {}
        duration = self._safe_float(payload.get("duration"))
        started_at = self._context.get("startedAt")

        run = dict(snapshot)
        run.update(
            {
                "hasRun": True,
                "startedLabel": (
                    started_at.strftime("%b %d, %Y · %H:%M:%S")
                    if isinstance(started_at, datetime)
                    else ""
                ),
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": "",
            }
        )
        self._run = run

        summary = dict(run.get("summary") or {})
        if str(run.get("operation") or "") == "save":
            persistence = dict(run.get("persistence") or {})
            self._set_message(
                "Registry Intelligence saved: "
                f"{int(persistence.get('evidencesCreated') or 0)} evidence, "
                f"{int(persistence.get('entitiesCreated') or 0)} entities, "
                f"{int(persistence.get('linksCreated') or 0)} links."
            )
        else:
            self._set_message(
                f"Registry search completed with {int(summary.get('records') or 0)} "
                f"record(s); {int(summary.get('blocked') or 0)} provider(s) blocked by policy/config."
            )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Unknown Registry error")
        duration = self._safe_float(payload.get("duration"))
        previous = dict(self._context.get("previous") or {})
        if bool(self._context.get("persist")) and previous:
            previous.update(
                {
                    "status": "failed",
                    "operation": "save",
                    "error": error,
                    "durationText": f"{duration:.1f}s",
                }
            )
            self._run = previous
        else:
            self._run.update(
                {
                    "hasRun": True,
                    "status": "failed",
                    "error": error,
                    "durationText": f"{duration:.1f}s",
                    "records": [],
                    "providers": [],
                }
            )
        self._set_message(f"Registry Intelligence failed: {error}")
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
