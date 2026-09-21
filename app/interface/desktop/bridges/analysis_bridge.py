from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from uuid import UUID, uuid4

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.application.analysis_history_service import AnalysisHistoryService
from app.application.analysis_chat_history_service import (
    AnalysisChatHistoryService,
)
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
from app.interface.desktop.workers.analysis_provider_discovery_worker import (
    AnalysisProviderDiscoveryWorker,
)
from app.interface.desktop.workers.analysis_chat_worker import (
    AnalysisChatWorker,
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
        self._provider_catalog = self._initial_provider_catalog()
        self._provider_thread: QThread | None = None
        self._provider_worker: AnalysisProviderDiscoveryWorker | None = None
        self._chat_messages: list[dict[str, Any]] = []
        self._chat_session_id = str(uuid4())
        self._chat_busy = False
        self._chat_thread: QThread | None = None
        self._chat_worker: AnalysisChatWorker | None = None

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property("QVariantList", notify=changed)
    def chatMessages(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._chat_messages]

    @Property(bool, notify=changed)
    def chatBusy(self) -> bool:
        return self._chat_busy

    @Property(str, notify=changed)
    def chatSessionId(self) -> str:
        return self._chat_session_id

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
        return dict(self._provider_entry(provider))

    @Property("QVariantList", notify=changed)
    def providerCatalog(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._provider_catalog]

    @Property(bool, notify=changed)
    def providerDiscoveryBusy(self) -> bool:
        return self._provider_thread is not None

    @Slot()
    def refreshProviders(self) -> None:
        """Refresh real local-provider state without blocking the QML thread."""

        if self._provider_thread is not None:
            return

        thread = QThread(self)
        worker = AnalysisProviderDiscoveryWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_provider_discovered)
        worker.failed.connect(self._on_provider_discovery_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.succeeded.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_provider_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._provider_thread = thread
        self._provider_worker = worker
        self.changed.emit()
        thread.start()

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
        self._chat_messages = []
        self._chat_session_id = str(uuid4())

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
        self._load_chat_history(normalized)
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

        return self._open_source_row(source, normalized)

    @Slot(str, str, result=bool)
    @Slot(
        str, str, str, str, str, str, str, str,
        result=bool,
    )
    @Slot(
        str, str, str, str, str, str, str, str, str,
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
        provider_name: str = "",
    ) -> bool:
        if self._busy or self._chat_busy:
            self._set_message(
                "Wait for the current AI operation to finish."
            )
            return False

        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            self._set_message(
                "Select an investigation before running analysis."
            )
            return False

        selected_provider = str(
            provider_name
            or settings.ai_provider
            or "ollama"
        ).strip().casefold()
        provider = self._provider_entry(selected_provider)
        if not provider:
            self._set_message(
                "Unsupported Analysis provider: " + selected_provider
            )
            return False

        if not provider.get("configured"):
            if selected_provider == "openai":
                self._set_message(
                    "OpenAI is selected but OPENAI_API_KEY is not configured."
                )
            else:
                self._set_message(
                    "Ollama is selected but no local Ollama endpoint is configured."
                )
            return False

        profile = normalize_analysis_mode(mode)
        selected_model = str(model or "").strip()
        if selected_provider == "openai":
            selected_model = normalize_openai_model(
                selected_model,
                fallback=profile.recommended_model,
            )
            selected_reasoning = normalize_reasoning_effort(
                reasoning_effort,
                fallback=profile.recommended_reasoning,
            )
        else:
            # Local providers own their model selection. A model chosen in the
            # UI is passed through; otherwise fall back to the configured
            # Ollama model without ever reusing stale GPT state.
            if not selected_model:
                selected_model = str(provider.get("model") or "").strip()
            if not selected_model:
                selected_model = str(
                    provider.get("defaultModel")
                    or ""
                ).strip()
            selected_reasoning = ""

        if not selected_model:
            self._set_message(
                "Select an AI model before running analysis."
            )
            return False

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
            "provider": selected_provider,
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
                "provider": selected_provider,
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
                provider_name=selected_provider,
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

    @Slot(
        str, str, str, str, str, str, str, str, str,
        result=bool,
    )
    def sendMessage(
        self,
        case_id: str,
        message: str,
        provider_name: str,
        model: str,
        reasoning_effort: str,
        mode: str,
        scope_type: str,
        focus_entity_id: str,
        focus_entity_label: str,
    ) -> bool:
        if self._busy or self._chat_busy:
            self._set_message("Wait for the current AI operation to finish.")
            return False

        normalized_case_id = str(case_id or "").strip()
        normalized_message = str(message or "").strip()
        if not normalized_case_id:
            self._set_message("Select an investigation before chatting with AI.")
            return False
        if not normalized_message:
            self._set_message("Enter a message for the AI assistant.")
            return False

        selected_provider = str(
            provider_name or settings.ai_provider or "ollama"
        ).strip().casefold()
        provider = self._provider_entry(selected_provider)
        if not provider:
            self._set_message(
                "Unsupported Analysis provider: " + selected_provider
            )
            return False
        if not provider.get("configured"):
            self._set_message(
                (
                    "OpenAI is selected but OPENAI_API_KEY is not configured."
                    if selected_provider == "openai"
                    else "Ollama is selected but no local endpoint is configured."
                )
            )
            return False
        if (
            selected_provider == "ollama"
            and provider.get("online") is not True
        ):
            self._set_message("Ollama is not currently available.")
            return False

        profile = normalize_analysis_mode(mode)
        selected_model = str(model or "").strip()
        if selected_provider == "openai":
            selected_model = normalize_openai_model(
                selected_model,
                fallback=profile.recommended_model,
            )
            selected_reasoning = normalize_reasoning_effort(
                reasoning_effort,
                fallback=profile.recommended_reasoning,
            )
        else:
            selected_reasoning = ""
            if not selected_model:
                selected_model = str(
                    provider.get("model")
                    or provider.get("defaultModel")
                    or ""
                ).strip()

        if not selected_model:
            self._set_message("Select an AI model before sending a message.")
            return False

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

        previous_conversation = [
            {
                "role": str(item.get("role") or ""),
                "text": str(item.get("text") or ""),
            }
            for item in self._chat_messages
            if isinstance(item, dict)
            and str(item.get("role") or "") in {"user", "assistant"}
        ]

        user_id = str(uuid4())
        self._chat_messages.append(
            {
                "id": user_id,
                "turnId": "",
                "role": "user",
                "text": normalized_message,
                "createdAt": datetime.now().isoformat(),
                "sourceReferences": [],
                "sources": [],
            }
        )
        self._chat_busy = True
        self._set_message("AI assistant is thinking…")
        self.changed.emit()

        try:
            thread = QThread(self)
            analysis_context = {
                "summary": str(self._run.get("summary") or ""),
                "conclusions": [
                    dict(item)
                    for item in list(self._run.get("conclusions") or [])
                    if isinstance(item, dict)
                ],
                "runConfig": dict(self._run.get("runConfig") or {}),
            }

            worker = AnalysisChatWorker(
                case_id=normalized_case_id,
                session_id=self._chat_session_id,
                message=normalized_message,
                conversation=previous_conversation,
                analysis_context=analysis_context,
                provider_name=selected_provider,
                model=selected_model,
                reasoning_effort=selected_reasoning,
                mode=profile.key,
                scope_type=normalized_scope,
                focus_entity_id=normalized_focus_id,
                focus_entity_label=normalized_focus_label,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_chat_succeeded)
            worker.failed.connect(self._on_chat_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_chat_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._chat_thread = thread
            self._chat_worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start Analysis chat worker")
            self._chat_busy = False
            self._chat_thread = None
            self._chat_worker = None
            self._set_message(
                "Unable to start AI chat: " + str(exc)
            )
            self.changed.emit()
            return False

    @Slot()
    def newChat(self) -> None:
        if self._busy or self._chat_busy:
            return
        self._chat_session_id = str(uuid4())
        self._chat_messages = []
        self._set_message("")
        self.changed.emit()

    @Slot(str, str, result=bool)
    def openChatSource(self, message_id: str, reference: str) -> bool:
        normalized_message = str(message_id or "").strip()
        normalized_reference = str(reference or "").strip()
        source: dict[str, Any] | None = None

        for message in self._chat_messages:
            if str(message.get("id") or "") != normalized_message:
                continue
            for item in list(message.get("sources") or []):
                if (
                    isinstance(item, dict)
                    and str(item.get("reference") or "") == normalized_reference
                ):
                    source = dict(item)
                    break
            if source is not None:
                break

        if source is None:
            self._set_message("The selected chat source is unavailable.")
            return False

        return self._open_source_row(source, normalized_reference)

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

    @Slot(object)
    def _on_chat_succeeded(self, result: object) -> None:
        payload = dict(result) if isinstance(result, dict) else {}
        message_id = (
            str(payload.get("turnId") or "")
            + ":assistant"
            if payload.get("turnId")
            else str(uuid4())
        )
        payload.update(
            {
                "id": message_id,
                "role": "assistant",
                "createdAt": datetime.now().isoformat(),
            }
        )
        self._chat_messages.append(payload)
        self._set_message("AI reply completed.")
        self.changed.emit()

    @Slot(object)
    def _on_chat_failed(self, result: object) -> None:
        payload = dict(result) if isinstance(result, dict) else {}
        error = str(payload.get("error") or "AI chat failed.")
        self._chat_messages.append(
            {
                "id": str(uuid4()),
                "turnId": "",
                "role": "assistant",
                "text": "I couldn't complete that reply. " + error,
                "createdAt": datetime.now().isoformat(),
                "sourceReferences": [],
                "sources": [],
                "warnings": [error],
                "error": True,
            }
        )
        self._set_message("AI chat failed: " + error)
        self.changed.emit()

    @Slot()
    def _on_chat_thread_finished(self) -> None:
        self._chat_busy = False
        self._chat_worker = None
        self._chat_thread = None
        self.changed.emit()

    @Slot(object)
    def _on_provider_discovered(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        online = bool(payload.get("ollamaOnline"))
        names = [
            str(value).strip()
            for value in list(payload.get("ollamaModels") or [])
            if str(value).strip()
        ]

        updated: list[dict[str, Any]] = []
        for item in self._provider_catalog:
            row = dict(item)
            if row.get("provider") == "ollama":
                row["online"] = online
                row["status"] = (
                    "online"
                    if online and names
                    else ("online_no_models" if online else "offline")
                )
                if online:
                    row["models"] = [
                        {
                            "id": name,
                            "label": name,
                            "tier": "Installed locally",
                        }
                        for name in names
                    ]
                    if names:
                        if (
                            str(row.get("defaultModel") or "") not in names
                        ):
                            row["defaultModel"] = names[0]
                            row["model"] = names[0]
                    else:
                        row["defaultModel"] = ""
                        row["model"] = ""
                row["discoveryError"] = str(
                    payload.get("ollamaError") or ""
                )
            updated.append(row)

        self._provider_catalog = updated
        self.changed.emit()

    @Slot(object)
    def _on_provider_discovery_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        self._set_message(
            str(payload.get("error") or "Unable to refresh AI providers.")
        )

    @Slot()
    def _on_provider_thread_finished(self) -> None:
        self._provider_worker = None
        self._provider_thread = None
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self._context = {}
        self.changed.emit()

    def _initial_provider_catalog(self) -> list[dict[str, Any]]:
        secret = settings.openai_api_key
        configured = bool(
            secret
            and secret.get_secret_value().strip()
        )

        openai_models = [
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("label") or item.get("id") or ""),
                "tier": str(item.get("tier") or ""),
            }
            for item in list(self._catalog.get("models") or [])
            if isinstance(item, dict)
        ]

        ollama_model = str(
            settings.ollama_model
            or settings.ai_model
            or settings.default_model
            or ""
        ).strip()
        ollama_models = (
            [
                {
                    "id": ollama_model,
                    "label": ollama_model,
                    "tier": "Configured local model",
                }
            ]
            if ollama_model
            else []
        )

        return [
            {
                "provider": "openai",
                "label": "OpenAI",
                "configured": configured,
                "online": None,
                "status": (
                    "configured"
                    if configured
                    else "not_configured"
                ),
                "model": str(settings.openai_model or ""),
                "defaultModel": str(settings.openai_model or ""),
                "models": openai_models,
                "reasoningEfforts": list(
                    self._catalog.get("reasoningEfforts") or []
                ),
                "reasoningEffort": str(
                    settings.openai_reasoning_effort or "medium"
                ),
                "storeResponses": bool(
                    settings.openai_store_responses
                ),
            },
            {
                "provider": "ollama",
                "label": "Ollama",
                "configured": bool(
                    str(settings.ollama_host or "").strip()
                ),
                "online": None,
                "status": "checking",
                "model": ollama_model,
                "defaultModel": ollama_model,
                "models": ollama_models,
                "reasoningEfforts": [],
                "reasoningEffort": "",
                "storeResponses": False,
            },
        ]

    def _provider_entry(self, provider_name: str) -> dict[str, Any]:
        normalized = str(provider_name or "").strip().casefold()
        for item in self._provider_catalog:
            if str(item.get("provider") or "").strip().casefold() == normalized:
                return dict(item)
        return {}

    def _open_source_row(
        self,
        source: dict[str, Any],
        reference: str,
    ) -> bool:
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
            elif object_type in {"timeline", "timeline_event", "event"} and object_id:
                opened = bool(
                    bridge.focusWorkspaceRecord("timeline", object_id)
                )
            elif object_type == "evidence" and object_id:
                opened = bool(
                    bridge.focusWorkspaceRecord("evidence", object_id)
                )
            elif object_type in {"message", "document", "source", "file"}:
                opened = bool(bridge.navigateTo("evidence"))
            else:
                opened = bool(bridge.navigateTo("search"))
        except Exception:
            LOGGER.exception("Unable to navigate to Analysis source")
            opened = False

        if opened:
            self._set_message(
                "Opened source workspace for "
                + (str(reference or "").strip() or "selected source")
                + "."
            )
        else:
            self._set_message(
                "The source is listed in Analysis, but no dedicated "
                "detail route is available for this object type."
            )
        return opened

    def _load_chat_history(self, case_id: str) -> None:
        normalized = str(case_id or "").strip()
        if not normalized:
            self._chat_messages = []
            self._chat_session_id = str(uuid4())
            return

        from app.database.session import create_session

        session = None
        try:
            session = create_session()
            service = AnalysisChatHistoryService(session)
            payload = service.load_latest_session(
                normalized,
                limit_turns=30,
            )
            session.rollback()
            self._chat_session_id = str(
                payload.get("sessionId") or uuid4()
            )
            self._chat_messages = [
                dict(item)
                for item in list(payload.get("messages") or [])
                if isinstance(item, dict)
            ]
        except Exception:
            LOGGER.exception("Unable to load Analysis chat history")
            self._chat_session_id = str(uuid4())
            self._chat_messages = []
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

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
