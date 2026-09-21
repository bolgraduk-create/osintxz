from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.core.config import settings
from app.interface.desktop.workers.investigation_analysis_worker import (
    InvestigationAnalysisWorker,
)


LOGGER = logging.getLogger(__name__)


class AnalysisBridge(QObject):
    """QML state bridge for the canonical investigation analysis runner."""

    changed = Signal()
    messageChanged = Signal()

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: InvestigationAnalysisWorker | None = None
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

    @Slot(str, str, result=bool)
    def runAnalysis(
        self,
        case_id: str,
        question: str = "",
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

        normalized_question = str(question or "").strip()
        started_at = datetime.now()
        self._context = {
            "caseId": normalized_case_id,
            "question": normalized_question,
            "startedAt": started_at,
        }
        self._run = {
            "hasRun": True,
            "status": "running",
            "phase": "starting",
            "caseId": normalized_case_id,
            "question": normalized_question,
            "progress": 0.0,
            "progressText": "Starting investigation analysis…",
            "currentStage": "",
            "currentStageLabel": "",
            "stageIndex": 0,
            "stageCount": 0,
            "stages": [],
            "summary": "",
            "conclusions": [],
            "sources": [],
            "warnings": [],
            "error": "",
            "startedLabel": started_at.strftime(
                "%b %d, %Y · %H:%M:%S"
            ),
            "durationText": "Running…",
            "provider": provider,
        }
        self._busy = True
        self._set_message("Investigation analysis started.")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = InvestigationAnalysisWorker(
                case_id=normalized_case_id,
                question=normalized_question,
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
                f"Unable to start investigation analysis: {exc}"
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
                "durationText": f"{duration:.1f}s",
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
            f"({status}): {source_count} bounded source(s)."
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
                "durationText": f"{duration:.1f}s",
                "error": error,
            }
        )
        self._run = current
        self._set_message(f"Investigation analysis failed: {error}")
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
