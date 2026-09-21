from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.application.analysis_history_service import AnalysisHistoryService
from app.application.analysis_run_profile import (
    analysis_workspace_catalog,
    normalize_analysis_mode,
    normalize_openai_model,
    normalize_reasoning_effort,
)
from app.core.config import settings
from app.models.entity import EntityType
from app.interface.desktop.workers.investigation_analysis_worker import (
    InvestigationAnalysisWorker,
)


LOGGER = logging.getLogger(__name__)


class AnalysisBridge(QObject):
    """QML state bridge for the canonical investigation analysis runner."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(
        self,
        container: Any,
        desktop_bridge: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._container = container
        self._desktop_bridge = desktop_bridge
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: InvestigationAnalysisWorker | None = None
        self._context: dict[str, Any] = {}
        self._case_id = ""
        self._focus_options: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._catalog = analysis_workspace_catalog()

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property("QVariantMap", constant=True)
    def catalog(self) -> dict[str, Any]:
        return dict(self._catalog)

    @Property("QVariantList", notify=changed)
    def focusOptions(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._focus_options]

    @Property("QVariantList", notify=changed)
    def history(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._history]

    @Property("QVariantMap", notify=changed)
    def providerInfo(self) -> dict[str, Any]:
        provider = str(settings.ai_provider or "ollama").strip().casefold()

        if provider == "openai":
            secret = settings.openai_api_key
            configured = bool(
                secret
                and secret.get_secret_value().strip()
            )
            return {
                "provider": "openai",
                "label": "OpenAI",
                "model": str(settings.openai_model or ""),
                "configured": configured,
                "reasoningEffort": str(
                    settings.openai_reasoning_effort or "medium"
                ),
                "storeResponses": bool(
                    settings.openai_store_responses
                ),
                "status": (
                    "configured"
                    if configured
                    else "not_configured"
                ),
            }

        model = str(
            settings.ollama_model
            or settings.ai_model
            or settings.default_model
            or ""
        )
        return {
            "provider": "ollama",
            "label": "Ollama",
            "model": model,
            "configured": bool(str(settings.ollama_host or "").strip()),
            "reasoningEffort": "",
            "storeResponses": False,
            "status": "configured",
        }

    @Slot(str)
    def prepareCase(self, case_id: str) -> None:
        normalized = str(case_id or "").strip()
        if normalized == self._case_id and self._focus_options:
            self._load_history(normalized)
            self.changed.emit()
            return

        self._case_id = normalized
        self._focus_options = []
        self._history = []

        if not normalized:
            self.changed.emit()
            return

        self._focus_options = [
            {
                "id": "",
                "label": "Entire Investigation",
                "type": "case",
            }
        ]

        try:
            service = getattr(self._container, "entity_service", None)
            if service is not None:
                people = service.get_page(
                    limit=500,
                    offset=0,
                    case_id=UUID(normalized),
                    entity_types=(EntityType.PERSON,),
                )
                rows = [
                    {
                        "id": str(getattr(item, "id", "") or ""),
                        "label": str(
                            getattr(item, "value", "")
                            or "Unnamed person"
                        ),
                        "type": "person",
                    }
                    for item in people
                    if str(getattr(item, "id", "") or "")
                ]
                rows.sort(
                    key=lambda item: (
                        str(item["label"]).casefold(),
                        str(item["id"]),
                    )
                )
                self._focus_options.extend(rows)
        except Exception:
            LOGGER.exception("Unable to load Analysis focus people")
            self._set_message(
                "Analysis is available, but person focus options "
                "could not be loaded."
            )

        self._load_history(normalized)
        self.changed.emit()

    @Slot(str, result=bool)
    def openHistory(self, history_id: str) -> bool:
        normalized = str(history_id or "").strip()
        item = next(
            (
                row
                for row in self._history
                if str(row.get("historyId") or "") == normalized
            ),
            None,
        )
        if item is None:
            self._set_message("The selected analysis history item is unavailable.")
            return False

        self._run = dict(item)
        self._run["hasRun"] = True
        self._run["phase"] = "history"
        self._run["progress"] = 1.0
        self._run["progressText"] = "Viewing saved analysis history."
        self._run.setdefault("durationText", self._duration_text(
            self._run.get("durationSeconds")
        ))
        self._set_message("Saved analysis opened.")
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    def openSource(self, reference: str) -> bool:
        normalized = str(reference or "").strip()
        source = next(
            (
                row
                for row in list(self._run.get("sources") or [])
                if str(row.get("reference") or "") == normalized
            ),
            None,
        )
        if not isinstance(source, dict):
            self._set_message("The selected RAG source is unavailable.")
            return False

        object_type = str(source.get("objectType") or "").strip().casefold()
        object_id = str(source.get("objectId") or "").strip()
        bridge = self._desktop_bridge
        if bridge is None:
            self._set_message("Desktop source navigation is unavailable.")
            return False

        opened = False
        try:
            if object_type in {"entity", "person"} and object_id:
                opened = bool(bridge.openEntity(object_id))
                if not opened:
                    opened = bool(bridge.navigateTo("entities"))
            elif object_type == "report" and object_id:
                opened = bool(bridge.openReport(object_id))
            elif object_type in {
                "timeline",
                "timeline_event",
                "event",
            }:
                opened = bool(bridge.navigateTo("timeline"))
            elif object_type in {
                "evidence",
                "message",
                "document",
                "source",
                "file",
            }:
                opened = bool(bridge.navigateTo("evidence"))
            else:
                opened = bool(bridge.navigateTo("search"))
        except Exception:
            LOGGER.exception("Unable to navigate to Analysis source")
            opened = False

        if opened:
            self._set_message(
                "Opened source workspace for "
                + (normalized or "selected source")
                + "."
            )
        else:
            self._set_message(
                "The source is listed in Analysis, but no dedicated "
                "detail route is available for this object type."
            )
        return opened

    @Slot(str, str, result=bool)
    @Slot(
        str, str, str, str, str, str, str, str,
        result=bool,
    )
    def runAnalysis(
        self,
        case_id: str,
        question: str = "",
        mode: str = "standard",
        model: str = "",
        reasoning_effort: str = "",
        scope_type: str = "case",
        focus_entity_id: str = "",
        focus_entity_label: str = "",
    ) -> bool:
        if self._busy:
            self._set_message(
                "An investigation analysis is already running."
            )
            return False

        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            self._set_message(
                "Select an investigation before running analysis."
            )
            return False

        provider = self.providerInfo
        if (
            provider.get("provider") == "openai"
            and not provider.get("configured")
        ):
            self._set_message(
                "OpenAI is selected but OPENAI_API_KEY is not configured."
            )
            return False

        profile = normalize_analysis_mode(mode)
        selected_model = str(model or "").strip()
        if provider.get("provider") == "openai":
            selected_model = normalize_openai_model(
                selected_model,
                fallback=profile.recommended_model,
            )
        elif not selected_model:
            selected_model = str(provider.get("model") or "")

        selected_reasoning = normalize_reasoning_effort(
            reasoning_effort,
            fallback=profile.recommended_reasoning,
        )

        normalized_scope = str(scope_type or "case").strip().casefold()
        normalized_focus_id = str(focus_entity_id or "").strip()
        normalized_focus_label = str(focus_entity_label or "").strip()
        if (
            normalized_scope != "person"
            or not normalized_focus_id
            or not normalized_focus_label
        ):
            normalized_scope = "case"
            normalized_focus_id = ""
            normalized_focus_label = "Entire Investigation"

        normalized_question = str(question or "").strip()
        started_at = datetime.now()
        self._context = {
            "caseId": normalized_case_id,
            "question": normalized_question,
            "startedAt": started_at,
            "mode": profile.key,
            "model": selected_model,
            "reasoningEffort": selected_reasoning,
            "scopeType": normalized_scope,
            "focusEntityId": normalized_focus_id,
            "focusEntityLabel": normalized_focus_label,
        }
        self._run = {
            "hasRun": True,
            "status": "running",
            "phase": "starting",
            "caseId": normalized_case_id,
            "question": normalized_question,
            "scope": {
                "type": normalized_scope,
                "entityId": normalized_focus_id,
                "label": normalized_focus_label,
            },
            "runConfig": {
                "mode": profile.key,
                "modeLabel": profile.label,
                "model": selected_model,
                "reasoningEffort": selected_reasoning,
                "plannedAiRequests": profile.ai_request_count,
                "maxOutputTokensPerRequest": profile.max_output_tokens,
                "provider": str(provider.get("provider") or ""),
            },
            "progress": 0.0,
            "progressText": "Starting investigation analysis…",
            "currentStage": "",
            "currentStageLabel": "",
            "stageIndex": 0,
            "stageCount": 0,
            "stages": [],
            "summary": "",
            "conclusions": [],
            "facts": [],
            "sources": [],
            "warnings": [],
            "usage": {},
            "cost": {},
            "error": "",
            "startedLabel": started_at.strftime(
                "%b %d, %Y · %H:%M:%S"
            ),
            "durationText": "Running…",
            "provider": provider,
        }
        self._busy = True
        self._set_message(
            profile.label
            + " analysis started"
            + (
                " for " + normalized_focus_label
                if normalized_scope == "person"
                else "."
            )
        )
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = InvestigationAnalysisWorker(
                case_id=normalized_case_id,
                question=normalized_question,
                mode=profile.key,
                model=selected_model,
                reasoning_effort=selected_reasoning,
                scope_type=normalized_scope,
                focus_entity_id=normalized_focus_id,
                focus_entity_label=normalized_focus_label,
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
            LOGGER.exception("Unable to start investigation analysis worker")
            self._busy = False
            self._thread = None
            self._worker = None
            self._context = {}
            self._run.update(
                {
                    "status": "failed",
                    "phase": "failed",
                    "error": str(exc),
                    "progressText": str(exc),
                    "durationText": "0.0s",
                }
            )
            self._set_message(
                "Unable to start investigation analysis: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot()
    def clear(self) -> None:
        if self._busy:
            return
        self._run = {}
        self._context = {}
        self._set_message("")
        self.changed.emit()

    @Slot(object)
    def _on_progress(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        current = dict(self._run)
        if not current:
            return

        stage = str(payload.get("stage") or "")
        current.update(
            {
                "phase": str(
                    payload.get("eventType") or "running"
                ),
                "progress": float(
                    payload.get("progress") or 0.0
                ),
                "progressText": str(
                    payload.get("message")
                    or "Analyzing investigation…"
                ),
                "currentStage": stage,
                "currentStageLabel": self._label(stage),
                "stageIndex": int(
                    payload.get("stageIndex") or 0
                ),
                "stageCount": int(
                    payload.get("stageCount") or 0
                ),
            }
        )
        self._run = current
        self._set_message(current["progressText"])
        self.changed.emit()

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = (
            dict(payload.get("snapshot"))
            if isinstance(payload.get("snapshot"), dict)
            else {}
        )
        duration = self._safe_float(payload.get("duration"))

        snapshot.update(
            {
                "hasRun": True,
                "phase": "completed",
                "progress": 1.0,
                "progressText": (
                    "Investigation analysis completed."
                ),
                "durationSeconds": round(duration, 3),
                "durationText": self._duration_text(duration),
                "startedLabel": (
                    self._context["startedAt"].strftime(
                        "%b %d, %Y · %H:%M:%S"
                    )
                    if isinstance(
                        self._context.get("startedAt"),
                        datetime,
                    )
                    else ""
                ),
                "error": "",
            }
        )
        self._run = snapshot

        status = str(snapshot.get("status") or "completed")
        source_count = len(
            list(snapshot.get("sources") or [])
        )
        self._set_message(
            "Investigation analysis completed "
            + "(" + status + "): "
            + str(source_count)
            + " bounded source(s)."
        )
        self._load_history(
            str(snapshot.get("caseId") or self._case_id)
        )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        duration = self._safe_float(payload.get("duration"))
        error = str(
            payload.get("error")
            or "Investigation analysis failed."
        )
        current = dict(self._run)
        current.update(
            {
                "hasRun": True,
                "status": "failed",
                "phase": "failed",
                "progressText": error,
                "durationSeconds": round(duration, 3),
                "durationText": self._duration_text(duration),
                "error": error,
            }
        )
        self._run = current
        self._set_message("Investigation analysis failed: " + error)
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self._context = {}
        self.changed.emit()

    def _load_history(self, case_id: str) -> None:
        normalized = str(case_id or "").strip()
        if not normalized:
            self._history = []
            return

        from app.database.session import create_session

        session = None
        try:
            session = create_session()
            service = AnalysisHistoryService(session)
            self._history = service.list_for_case(
                normalized,
                limit=30,
            )
            session.rollback()
        except Exception:
            LOGGER.exception("Unable to load Analysis history")
            self._history = []
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

    def _set_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized == self._message:
            return
        self._message = normalized
        self.messageChanged.emit()

    @staticmethod
    def _label(value: str) -> str:
        return str(value or "").replace("_", " ").title()

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _duration_text(cls, value: Any) -> str:
        return format(cls._safe_float(value), ".1f") + "s"
