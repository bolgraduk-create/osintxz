"""
Case workspace page.

Responsible for:

- displaying selected investigation workspace
- connecting workspace data with views
- handling workspace actions
- displaying import results

Does NOT:

- execute business logic
- access database directly
"""

from __future__ import annotations

import logging
from threading import Event
from typing import Any
from uuid import UUID

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QInputDialog,
)

from app.interface.desktop.localization.translatable import (
    TranslatableMixin,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)

from app.interface.desktop.views.workspace.case_workspace_view import (
    CaseWorkspaceView,
)

from app.interface.desktop.dialogs.ai_result_dialog import (
    AIResultDialog,
)

from app.application.investigation_action import (
    InvestigationActionRequest,
    InvestigationActionType,
)

from app.application.investigation_analysis_contracts import (
    InvestigationAnalysisProgressEvent,
    InvestigationAnalysisProgressEventType,
    InvestigationAnalysisStage,
    InvestigationAnalysisRequest,
    InvestigationAnalysisResult,
)

from app.interface.desktop.dialogs.similar_images_dialog import (
    SimilarImagesDialog,
)

from app.interface.desktop.dialogs.similar_faces_dialog import (
    SimilarFacesDialog,
)

from app.interface.desktop.dialogs.select_location_photos_dialog import (
    SelectLocationPhotosDialog,
)

from app.osint import result

from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)

from app.interface.desktop.workers import (
    AIRequestWorker,
)

from app.interface.desktop.workers.investigation_search_worker import (
    InvestigationSearchWorker,
)

from app.models.evidence import (
    EvidenceType,
)


logger = logging.getLogger(
    __name__
)


class _InvestigationAnalysisCancellationToken:
    """
    Thread-safe cooperative cancellation token for one analysis run.

    The orchestrator only depends on ``is_cancelled()``.  The page owns
    the mutable ``cancel()`` side so the GUI thread can request stopping
    without terminating the worker QThread.
    """

    def __init__(
        self,
    ) -> None:

        self._cancel_event = Event()

    def cancel(
        self,
    ) -> None:
        """Request cooperative cancellation."""

        self._cancel_event.set()

    def is_cancelled(
        self,
    ) -> bool:
        """Return whether cancellation has been requested."""

        return self._cancel_event.is_set()


class CaseWorkspacePage(
    TranslatableMixin,
    BasePage,
):
    """
    Workspace for selected case.
    """

    # Soft per-stage watchdog.  It requests cooperative cancellation
    # instead of terminating a QThread.  Tests may temporarily lower
    # this value; production keeps a conservative five-minute limit.
    INVESTIGATION_ANALYSIS_STAGE_TIMEOUT_MS = 300_000

    # Apply the soft watchdog only to analytical / AI stages that may
    # legitimately be expensive. CASE_VALIDATION and UNIFIED_CONTEXT are
    # deliberately excluded so a slow database lookup or final aggregation
    # cannot consume the heavy-stage deadline before analysis has begun.
    INVESTIGATION_ANALYSIS_TIMEOUT_GUARDED_STAGES = frozenset(
        {
            InvestigationAnalysisStage.ENTITY_RESOLUTION,
            InvestigationAnalysisStage.EVIDENCE,
            InvestigationAnalysisStage.GRAPH,
            InvestigationAnalysisStage.TEMPORAL,
            InvestigationAnalysisStage.ANOMALY,
            InvestigationAnalysisStage.CLUSTERING,
            InvestigationAnalysisStage.RAG,
        }
    )

    # Thread-safe bridge for progress events emitted while the
    # orchestrator is executing inside the background worker thread.
    investigation_analysis_progress = Signal(object)

    def __init__(
        self,
        container,
    ) -> None:

        self.container = container

        self.case: dict[str, Any] | None = None

        self._investigation_search_thread: QThread | None = None
        self._investigation_search_worker: InvestigationSearchWorker | None = None
        self._latest_investigation_search_payload: dict | None = None

        self._ai_thread: QThread | None = None

        self._ai_worker: AIRequestWorker | None = None

        # Full investigation analysis uses the same established
        # QThread + callable-worker desktop pattern as AI requests,
        # but has an independent lifecycle so chat/workflow requests
        # cannot overwrite its thread/worker references.
        self._analysis_thread: QThread | None = None

        self._analysis_worker: AIRequestWorker | None = None

        self._analysis_cancellation_token: (
            _InvestigationAnalysisCancellationToken
            | None
        ) = None

        self._analysis_stage_timeout_timer: QTimer | None = None

        self._analysis_timeout_triggered = False

        self._latest_investigation_analysis_result: (
            InvestigationAnalysisResult
            | None
        ) = None

        self._latest_investigation_analysis_error: str | None = None

        self._latest_investigation_analysis_progress: (
            InvestigationAnalysisProgressEvent
            | None
        ) = None

        self._investigation_analysis_progress_history: list[
            InvestigationAnalysisProgressEvent
        ] = []

        super().__init__(
            "Case Workspace"
        )

        # QObject/QWidget base initialization must happen before
        # creating child QObject instances with self as parent.
        self._analysis_stage_timeout_timer = QTimer(
            self
        )

        self._analysis_stage_timeout_timer.setSingleShot(
            True
        )

        self._analysis_stage_timeout_timer.timeout.connect(
            self._on_investigation_analysis_stage_timeout
        )

        # Always queue progress delivery onto the page/UI thread.
        # The callback passed to the orchestrator may be invoked from
        # the background worker thread and must never update UI state
        # directly.
        self.investigation_analysis_progress.connect(
            self._on_investigation_analysis_progress,
            Qt.ConnectionType.QueuedConnection,
        )

        self.initialize_translations(
            self.container.translation_manager
        )

    # ==========================================================
    # Background investigation analysis
    # ==========================================================

    @property
    def investigation_analysis_running(
        self,
    ) -> bool:
        """
        Return whether the full investigation analysis thread is active.

        The actual duplicate-click UI policy is implemented later in the
        dedicated single-active-analysis stage.  This property exposes the
        lifecycle state without coupling the orchestrator to Qt.
        """

        return bool(
            self._analysis_thread is not None
            and self._analysis_thread.isRunning()
        )

    @property
    def investigation_analysis_cancellation_requested(
        self,
    ) -> bool:
        """Return whether cancellation was requested for the active run."""

        token = self._analysis_cancellation_token

        return bool(
            token is not None
            and token.is_cancelled()
        )

    @property
    def investigation_analysis_timeout_triggered(
        self,
    ) -> bool:
        """Return whether the current/last run exceeded a stage guard."""

        return bool(
            self._analysis_timeout_triggered
        )

    def cancel_investigation_analysis(
        self,
    ) -> bool:
        """
        Request cooperative cancellation of the active full analysis.

        No QThread termination is performed. The orchestrator observes the
        token between stages, marks remaining stages CANCELLED and returns a
        normal InvestigationAnalysisResult with status=CANCELLED.

        Returns True when a live run received the request, otherwise False.
        """

        token = self._analysis_cancellation_token

        if (
            token is None
            or not self.investigation_analysis_running
        ):

            return False

        token.cancel()

        return True

    @property
    def latest_investigation_analysis_result(
        self,
    ) -> InvestigationAnalysisResult | None:
        """
        Return the most recent successful background analysis result.
        """

        return self._latest_investigation_analysis_result

    @property
    def latest_investigation_analysis_error(
        self,
    ) -> str | None:
        """
        Return the most recent worker-level background execution error.
        """

        return self._latest_investigation_analysis_error

    @property
    def latest_investigation_analysis_progress(
        self,
    ) -> InvestigationAnalysisProgressEvent | None:
        """
        Return the most recently delivered orchestrator progress event.
        """

        return self._latest_investigation_analysis_progress

    @property
    def investigation_analysis_progress_history(
        self,
    ) -> tuple[InvestigationAnalysisProgressEvent, ...]:
        """
        Return progress events delivered during the current/last run.
        """

        return tuple(
            self._investigation_analysis_progress_history
        )

    def start_investigation_analysis_background(
        self,
        request: InvestigationAnalysisRequest,
    ) -> None:
        """
        Execute the production orchestrator outside the Qt UI thread.

        This method deliberately reuses the application's existing
        ``QThread + AIRequestWorker`` pattern.  AIRequestWorker is a generic
        callable worker despite its historical name; it does not build AI
        prompts or own an AI provider.

        No Analyze button is connected here yet.  UI action wiring belongs
        to the later integration block; this stage establishes only the
        background execution boundary and lifecycle.
        """

        if not isinstance(
            request,
            InvestigationAnalysisRequest,
        ):

            raise TypeError(
                "request must be InvestigationAnalysisRequest."
            )

        # A live QThread reference must never be overwritten.  The later
        # single-active-analysis stage will add the user-facing button policy.
        if self.investigation_analysis_running:

            raise RuntimeError(
                "Investigation analysis is already running."
            )

        orchestrator = getattr(
            self.container,
            "investigation_analysis_orchestrator",
            None,
        )

        if orchestrator is None:

            raise RuntimeError(
                "InvestigationAnalysisOrchestrator is unavailable."
            )

        analyze = getattr(
            orchestrator,
            "analyze",
            None,
        )

        if not callable(
            analyze
        ):

            raise RuntimeError(
                "InvestigationAnalysisOrchestrator.analyze is unavailable."
            )

        self._latest_investigation_analysis_result = None
        self._latest_investigation_analysis_error = None
        self._latest_investigation_analysis_progress = None
        self._investigation_analysis_progress_history = []

        self._analysis_timeout_triggered = False
        self._analysis_stage_timeout_timer.stop()

        cancellation_token = (
            _InvestigationAnalysisCancellationToken()
        )

        self._analysis_cancellation_token = cancellation_token

        thread = QThread(
            self
        )

        worker = AIRequestWorker(
            operation=analyze,
            operation_kwargs={
                "request": request,
                "progress_callback": (
                    self._emit_investigation_analysis_progress
                ),
                "cancellation_token": cancellation_token,
            },
        )

        self._analysis_thread = thread
        self._analysis_worker = worker

        worker.moveToThread(
            thread
        )

        thread.started.connect(
            worker.run
        )

        worker.succeeded.connect(
            self._on_investigation_analysis_succeeded
        )

        worker.failed.connect(
            self._on_investigation_analysis_failed
        )

        worker.finished.connect(
            thread.quit
        )

        worker.finished.connect(
            worker.deleteLater
        )

        thread.finished.connect(
            self._on_investigation_analysis_thread_finished
        )

        thread.finished.connect(
            thread.deleteLater
        )

        # Block 7 UI integration: preserve the existing AI Assistant UX
        # while routing its Analyze action through the orchestrator.
        self.workspace_view.set_ai_loading(
            True
        )

        self.workspace_view.set_analysis_status(
            self.translate(
                "workspace.analysis.starting",
                default="Starting analysis...",
            )
        )

        thread.start()

    def _emit_investigation_analysis_progress(
        self,
        event: InvestigationAnalysisProgressEvent,
    ) -> None:
        """
        Bridge one orchestrator progress callback into Qt.

        This callable is intentionally safe to invoke from the worker
        thread. It performs no widget access and no page-state mutation;
        it only emits a queued Qt signal.
        """

        if not isinstance(
            event,
            InvestigationAnalysisProgressEvent,
        ):

            return

        self.investigation_analysis_progress.emit(
            event
        )

    @Slot(object)
    def _on_investigation_analysis_progress(
        self,
        event: object,
    ) -> None:
        """
        Store one progress event on the UI thread.

        Rendering is intentionally deferred to the dedicated progress UI
        stage. This method establishes the safe worker-to-UI boundary.
        """

        if not isinstance(
            event,
            InvestigationAnalysisProgressEvent,
        ):

            return

        self._latest_investigation_analysis_progress = event
        self._investigation_analysis_progress_history.append(
            event
        )

        self._update_investigation_analysis_progress_ui(
            event
        )

        if (
            event.event_type
            == InvestigationAnalysisProgressEventType.STAGE_STARTED
        ):

            # Reset any previous stage deadline first. Only explicitly
            # guarded heavy stages receive a watchdog. Lightweight
            # validation/final aggregation must not trigger this policy.
            self._analysis_stage_timeout_timer.stop()

            if (
                event.stage
                in self.INVESTIGATION_ANALYSIS_TIMEOUT_GUARDED_STAGES
            ):

                self._analysis_stage_timeout_timer.start(
                    int(
                        self.INVESTIGATION_ANALYSIS_STAGE_TIMEOUT_MS
                    )
                )

        elif (
            event.event_type
            in {
                InvestigationAnalysisProgressEventType.STAGE_FINISHED,
                InvestigationAnalysisProgressEventType.ANALYSIS_FINISHED,
            }
        ):

            self._analysis_stage_timeout_timer.stop()

    @Slot()
    def _on_investigation_analysis_stage_timeout(
        self,
    ) -> None:
        """Request cooperative cancellation after a stage deadline."""

        if not self.investigation_analysis_running:

            return

        self._analysis_timeout_triggered = True

        self.cancel_investigation_analysis()

    def _on_investigation_analysis_succeeded(
        self,
        result: object,
    ) -> None:
        """
        Capture one completed production analysis result on the UI thread.

        Rendering is intentionally deferred to the later results/UI block.
        """

        if not isinstance(
            result,
            InvestigationAnalysisResult,
        ):

            self._latest_investigation_analysis_result = None
            self._latest_investigation_analysis_error = (
                "Background investigation analysis returned an invalid "
                "result type."
            )

            return

        self._latest_investigation_analysis_result = result
        self._latest_investigation_analysis_error = None

        self._render_investigation_analysis_result(
            result
        )

    def _on_investigation_analysis_failed(
        self,
        error_message: str,
    ) -> None:
        """
        Capture one worker-level execution failure on the UI thread.

        Stage-level analytical failures remain represented inside
        InvestigationAnalysisResult and are not converted into worker errors.
        """

        normalized_error = str(
            error_message
            or ""
        ).strip()

        self._latest_investigation_analysis_result = None
        self._latest_investigation_analysis_error = (
            normalized_error
            or "Unknown investigation analysis worker error."
        )

        logger.error(
            "Investigation analysis worker failed: %s",
            self._latest_investigation_analysis_error,
        )

        user_message = (
            self._normalize_investigation_analysis_error(
                self._latest_investigation_analysis_error
            )
        )

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.error_role",
                    default="Error",
                ),
                text=user_message,
            )
        )

        self.workspace_view.set_analysis_status(
            user_message
        )

    def _on_investigation_analysis_thread_finished(
        self,
    ) -> None:
        """
        Release background analysis thread/worker references.
        """

        self._analysis_stage_timeout_timer.stop()

        self._analysis_worker = None
        self._analysis_thread = None
        self._analysis_cancellation_token = None

        self.workspace_view.set_ai_loading(
            False
        )

        self.workspace_view.set_analysis_status(
            self._final_investigation_analysis_status_text()
        )

    # ==========================================================
    # Block 7: orchestrator -> existing AI workspace UI
    # ==========================================================

    def _update_investigation_analysis_progress_ui(
        self,
        event: InvestigationAnalysisProgressEvent,
    ) -> None:
        """Render lightweight progress in the existing workspace chrome."""

        event_type = event.event_type

        if (
            event_type
            == InvestigationAnalysisProgressEventType.ANALYSIS_STARTED
        ):

            text = self.translate(
                "workspace.analysis.running",
                default="Analysis started...",
            )

        elif (
            event_type
            == InvestigationAnalysisProgressEventType.STAGE_STARTED
        ):

            stage_name = (
                event.stage.value.replace("_", " ").title()
                if event.stage is not None
                else "Analysis"
            )

            if event.stage_count:
                text = (
                    f"Analyzing: {stage_name} "
                    f"({event.stage_index}/{event.stage_count})"
                )
            else:
                text = f"Analyzing: {stage_name}"

        elif (
            event_type
            == InvestigationAnalysisProgressEventType.ANALYSIS_FINISHED
        ):

            text = self.translate(
                "workspace.analysis.finalizing",
                default="Analysis finished. Preparing results...",
            )

        else:
            return

        self.workspace_view.set_analysis_status(
            text
        )

    def _render_investigation_analysis_result(
        self,
        result: InvestigationAnalysisResult,
    ) -> None:
        """Render one orchestrator result inside the existing AI Assistant."""

        sections: list[str] = []

        status_value = str(
            getattr(result.status, "value", result.status)
        )

        if status_value == "partial":
            sections.append(
                "Analysis completed with partial results. "
                "Successful sections are shown below."
            )
        elif status_value == "cancelled":
            sections.append(
                "Analysis was cancelled. Results completed before "
                "cancellation are shown below."
            )
        elif status_value == "failed":
            sections.append(
                "Analysis could not complete its analytical stages."
            )

        context = result.unified_context
        rag = getattr(context, "rag", None)

        summary = getattr(rag, "summary", None)
        if summary is not None:
            summary_text = str(
                getattr(summary, "summary", "")
                or ""
            ).strip()

            if summary_text:
                sections.append(
                    "SUMMARY\n"
                    + summary_text
                )
            elif getattr(summary, "status", None) == "insufficient_context":
                sections.append(
                    "SUMMARY\n"
                    "Not enough investigation context was available "
                    "to generate an AI summary."
                )

            references = tuple(
                getattr(summary, "source_references", ())
                or ()
            )
            if references:
                sections.append(
                    "SUMMARY SOURCES\n"
                    + ", ".join(references)
                )

        conclusions = getattr(rag, "conclusions", None)
        if conclusions is not None:
            rendered_conclusions: list[str] = []

            headings = {
                "hypotheses": "HYPOTHESES",
                "contradictions": "CONTRADICTIONS",
                "next_steps": "NEXT STEPS",
            }

            for conclusion in tuple(
                getattr(conclusions, "conclusions", ())
                or ()
            ):
                kind = getattr(
                    getattr(conclusion, "kind", None),
                    "value",
                    str(getattr(conclusion, "kind", "conclusion")),
                )
                text = str(
                    getattr(conclusion, "text", "")
                    or ""
                ).strip()

                if not text:
                    continue

                block = (
                    headings.get(kind, str(kind).upper())
                    + "\n"
                    + text
                )

                refs = tuple(
                    getattr(conclusion, "source_references", ())
                    or ()
                )
                if refs:
                    block += (
                        "\nSources: "
                        + ", ".join(refs)
                    )

                rendered_conclusions.append(block)

            sections.extend(rendered_conclusions)

        citation_lines = self._format_investigation_citation_status(
            rag
        )
        if citation_lines:
            sections.append(
                "SOURCE VALIDATION\n"
                + "\n".join(citation_lines)
            )

        available_sections = tuple(
            getattr(context, "available_sections", ())
            or ()
        )
        if available_sections:
            sections.append(
                "AVAILABLE ANALYTICAL SECTIONS\n"
                + ", ".join(available_sections)
            )

        failed_stages = []
        for stage_result in result.stage_results:
            status = str(
                getattr(stage_result.status, "value", stage_result.status)
            )
            if status != "failed":
                continue

            stage_name = stage_result.stage.value.replace("_", " ").title()
            message = (
                str(getattr(stage_result.error, "message", "") or "")
                .strip()
            )
            if not message:
                message = "This analysis stage was unavailable."
            failed_stages.append(
                f"{stage_name}: {message}"
            )

        if failed_stages:
            sections.append(
                "PARTIAL ANALYSIS WARNINGS\n"
                + "\n".join(failed_stages)
            )

        warnings = tuple(result.warnings or ())
        if warnings:
            sections.append(
                "WARNINGS\n"
                + "\n".join(str(item) for item in warnings)
            )

        if not sections:
            sections.append(
                "Analysis completed, but no displayable result was produced."
            )

        rendered = "\n\n".join(sections)

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.assistant_role",
                    default="AI",
                ),
                text=rendered,
            )
        )

        self.workspace_view.show_ai_tab()

    @staticmethod
    def _format_investigation_citation_status(
        rag: object | None,
    ) -> list[str]:
        """Return compact R1/R2 citation/provenance state lines."""

        if rag is None:
            return []

        lines: list[str] = []

        summary_validation = getattr(
            rag,
            "summary_citations",
            None,
        )

        if summary_validation is not None:
            for citation in tuple(
                getattr(summary_validation, "citations", ())
                or ()
            ):
                status = getattr(
                    getattr(citation, "status", None),
                    "value",
                    str(getattr(citation, "status", "unknown")),
                )
                lines.append(
                    f"Summary {citation.reference_id}: {status}"
                )

        conclusions_validation = getattr(
            rag,
            "conclusions_citations",
            None,
        )

        if conclusions_validation is not None:
            for item in tuple(
                getattr(conclusions_validation, "items", ())
                or ()
            ):
                workflow_name = str(
                    getattr(item, "workflow_name", "conclusion")
                )
                validation = getattr(item, "validation", None)
                for citation in tuple(
                    getattr(validation, "citations", ())
                    or ()
                ):
                    status = getattr(
                        getattr(citation, "status", None),
                        "value",
                        str(getattr(citation, "status", "unknown")),
                    )
                    lines.append(
                        f"{workflow_name} {citation.reference_id}: {status}"
                    )

        return lines

    @staticmethod
    def _normalize_investigation_analysis_error(
        error_message: str,
    ) -> str:
        """Convert a worker/internal error into a short user message."""

        normalized = str(error_message or "").strip()
        lowered = normalized.lower()

        if "ollama" in lowered or "connectionerror" in lowered:
            return (
                "AI analysis is currently unavailable. "
                "Non-AI analytical results may still be available "
                "from a partial run."
            )

        if "already running" in lowered:
            return "An investigation analysis is already running."

        if "cancel" in lowered:
            return "Investigation analysis was cancelled."

        return (
            "Investigation analysis could not be completed. "
            "Technical details were written to the application log."
        )

    def _final_investigation_analysis_status_text(
        self,
    ) -> str:
        """Return a stable final status for the existing workspace status bar."""

        result = self._latest_investigation_analysis_result

        if result is None:
            if self._latest_investigation_analysis_error:
                return self.translate(
                    "workspace.analysis.failed",
                    default="Analysis failed",
                )
            return self.translate(
                "workspace.loaded",
                default="Workspace loaded",
            )

        status = str(
            getattr(result.status, "value", result.status)
        )

        return {
            "success": "Analysis completed",
            "partial": "Analysis completed with partial results",
            "cancelled": "Analysis cancelled",
            "failed": "Analysis failed",
        }.get(status, "Analysis completed")

    def _start_orchestrated_analysis_from_ui(
        self,
        *,
        question: str | None,
        source: str,
    ) -> None:
        """Single Block-7 entry point used by Analyze and quick actions."""

        if self.case is None:
            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.ai.dialog_title",
                    default="AI assistant",
                ),
                self.translate(
                    "workspace.errors.no_case",
                    default="No investigation selected.",
                ),
            )
            return

        case_id = self.case.get("id")
        if case_id is None:
            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.ai.dialog_title",
                    default="AI assistant",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default="The selected investigation does not contain an identifier.",
                ),
            )
            return

        normalized_question = str(question or "").strip() or None

        request = InvestigationAnalysisRequest(
            case_id=case_id,
            question=normalized_question,
            requested_stages=None,
            metadata={
                "ui_source": source,
                "ui": "case_workspace_ai_assistant",
            },
        )

        try:
            self.start_investigation_analysis_background(
                request
            )
        except RuntimeError as exc:
            user_message = self._normalize_investigation_analysis_error(
                str(exc)
            )
            QMessageBox.information(
                self,
                self.translate(
                    "workspace.ai.dialog_title",
                    default="AI assistant",
                ),
                user_message,
            )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create case workspace UI.
        """

        self.setObjectName(
            "CaseWorkspacePage"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.setSpacing(
            0
        )

        self.workspace_view = (
            CaseWorkspaceView(
                translation_manager=(
                    self.container.translation_manager
                ),
                parent=self,
            )
        )

        self.workspace_view.investigation_search_requested.connect(
            self._start_investigation_search
        )

        self.workspace_view.import_telegram_requested.connect(
            self._import_telegram
        )

        self.workspace_view.refresh_requested.connect(
            self._refresh_workspace
        )

        self.workspace_view.import_files_requested.connect(
            self._import_files
        )

        self.workspace_view.create_evidence_requested.connect(
            self._create_evidence_from_message
        )

        self.workspace_view.create_entity_requested.connect(
            self._create_entity_from_message
        )

        self.workspace_view.add_timeline_event_requested.connect(
            self._create_timeline_from_message
        )

        self.main_layout.addWidget(
            self.workspace_view
        )

        self.workspace_view.bulk_message_action_requested.connect(
            self._handle_bulk_message_action
        )

        self.workspace_view.ai_analysis_requested.connect(
            self._analyze_message_with_ai
        )

        self.workspace_view.ai_question_requested.connect(
            self._ask_ai_question
        )

        self.workspace_view.ai_workflow_requested.connect(
            self._run_ai_workflow
        )

        self.workspace_view.calculate_image_hashes_requested.connect(
            self._calculate_image_hashes
        )

        self.workspace_view.find_similar_images_requested.connect(
            self._find_similar_images
        )

        self.workspace_view.compare_images_requested.connect(
            self._compare_images
        )

        self.workspace_view.detect_faces_requested.connect(
            self._detect_faces
        )

        self.workspace_view.find_face_matches_requested.connect(
            self._find_face_matches
        )

        self.workspace_view.create_location_requested.connect(
            self._create_location_from_gps
        )

        self.workspace_view.edit_location_requested.connect(
            self._edit_location
        )

        self.workspace_view.location_photos_requested.connect(
            self._load_location_photos
        )

        self.workspace_view.attach_location_photo_requested.connect(
            self._attach_location_photo
        )

        self.workspace_view.detach_location_photo_requested.connect(
            self._detach_location_photo
        )

        self.workspace_view.open_location_photo_requested.connect(
            self._open_location_photo
        )

    # ==========================================================
    # Investigation Search
    # ==========================================================

    def _start_investigation_search(
        self,
        raw_target: str,
        recursive: bool,
    ) -> None:
        if self.case is None:
            return

        if (
            self._investigation_search_thread is not None
            and self._investigation_search_thread.isRunning()
        ):
            self.workspace_view.investigation_search_view.set_status(
                "Поиск уже выполняется."
            )
            return

        raw_case_id = self.case.get("id")
        if raw_case_id is None:
            self.workspace_view.investigation_search_view.show_error(
                "У текущего дела отсутствует case_id."
            )
            return

        try:
            case_id = UUID(str(raw_case_id))
        except (TypeError, ValueError):
            self.workspace_view.investigation_search_view.show_error(
                "Некорректный case_id."
            )
            return

        view = self.workspace_view.investigation_search_view
        view.clear_results()
        view.set_running(True)

        thread = QThread(self)
        worker = InvestigationSearchWorker(
            container=self.container,
            case_id=case_id,
            raw_target=raw_target,
            recursive=recursive,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.status_changed.connect(view.set_status)
        worker.result_ready.connect(
            self._on_investigation_search_result
        )
        worker.failed.connect(
            self._on_investigation_search_error
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(
            self._on_investigation_search_thread_finished
        )
        thread.finished.connect(thread.deleteLater)

        self._investigation_search_thread = thread
        self._investigation_search_worker = worker
        thread.start()

    @Slot(object)
    def _on_investigation_search_result(
        self,
        payload,
    ) -> None:
        self._latest_investigation_search_payload = payload

        try:
            self.container.commit()
        except Exception as exc:
            logger.exception("Investigation Search commit failed.")
            try:
                self.container.rollback()
            except Exception:
                logger.exception("Investigation Search rollback failed.")

            self.workspace_view.investigation_search_view.show_error(
                f"Не удалось сохранить результаты: {exc}"
            )
            return

        self.workspace_view.investigation_search_view.show_result(
            payload
        )

        try:
            self._refresh_workspace()
        except Exception:
            logger.exception(
                "Workspace refresh after Investigation Search failed."
            )

    @Slot(str)
    def _on_investigation_search_error(
        self,
        message: str,
    ) -> None:
        try:
            self.container.rollback()
        except Exception:
            logger.exception("Investigation Search rollback failed.")

        self.workspace_view.investigation_search_view.show_error(
            message
        )

    @Slot()
    def _on_investigation_search_thread_finished(
        self,
    ) -> None:
        self._investigation_search_worker = None
        self._investigation_search_thread = None

        view = getattr(
            self.workspace_view,
            "investigation_search_view",
            None,
        )
        if view is not None:
            view.set_running(False)

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply current language to page metadata.
        """

        self.title = self.translate(
            "navigation.case_workspace",
            default="Case Workspace",
        )

    # ==========================================================
    # Loading
    # ==========================================================

    def load_case(
        self,
        case: dict[str, Any],
    ) -> None:
        """
        Load selected investigation workspace.
        """

        if not isinstance(
            case,
            dict,
        ):

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.invalid_case",
                    default="Invalid investigation data.",
                ),
            )

            return

        case_id = case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        self.case = dict(
            case
        )

        self.workspace_view.set_loading(
            True
        )

        try:

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.load_failed",
                    default=(
                        "Investigation workspace could not "
                        "be loaded.\n\n{error}"
                    ),
                    error=str(exc),
                ),
            )

            return

        finally:

            self.workspace_view.set_loading(
                False
            )

        if not isinstance(
            workspace,
            dict,
        ):

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.load_unavailable",
                    default=(
                        "Investigation workspace could not "
                        "be loaded."
                    ),
                ),
            )

            return

        self._display_workspace(
            workspace
        )

    def _display_workspace(
        self,
        workspace: dict[str, Any],
    ) -> None:
        """
        Send prepared workspace data to the workspace view.
        """

        self.workspace_view.set_workspace_data(
            workspace
        )

    # ==========================================================
    # Refresh
    # ==========================================================

    def refresh(
        self,
    ) -> None:
        """
        Public page refresh method.
        """

        self._refresh_workspace()

    def _refresh_workspace(
        self,
    ) -> None:
        """
        Reload current investigation workspace.
        """

        if self.case is None:

            return

        self.load_case(
            self.case
        )

    def _dispatch_investigation_action(
        self,
        request: InvestigationActionRequest,
    ) -> None:
        """
        Dispatch a workspace investigation action.
        """

        if self.case is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.no_case",
                    default="No investigation selected.",
                ),
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        handlers = {
            InvestigationActionType.CREATE_EVIDENCE: (
                self._execute_create_evidence_action
            ),

            InvestigationActionType.CREATE_ENTITY: (
                self._execute_create_entity_action
            ),

            InvestigationActionType.ADD_TIMELINE_EVENT: (
                self._execute_create_timeline_action
            ),

            InvestigationActionType.ANALYZE_WITH_AI: (
                self._execute_message_ai_analysis
            ),
        }

        handler = handlers.get(
            request.action_type
        )

        if handler is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.actions.unsupported",
                    default="This investigation action is not supported yet.",
                ),
            )

            return

        self.workspace_view.set_loading(
            True
        )

        try:

            handler(
                case_id=case_id,
                request=request,
            )

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.actions.failed_title",
                    default="Investigation action failed",
                ),
                str(
                    exc
                ),
            )

        finally:

            self.workspace_view.set_loading(
                False
            )

    def _execute_create_evidence_action(
        self,
        *,
        case_id,
        request: InvestigationActionRequest,
    ) -> None:
        """
        Execute evidence creation from an investigation action.
        """

        result = (
            self.container
            .workspace_controller
            .create_evidence_from_message(
                case_id=case_id,
                message_data=request.payload,
            )
        )

        self.workspace_view.show_evidence_tab()

        evidence_data = (
            result.get(
                "evidence",
                {},
            )
            if isinstance(
                result,
                dict,
            )
            else {}
        )

        evidence_title = str(
            evidence_data.get(
                "title"
            )
            or self.translate(
                "workspace.evidence.created_default",
                default="Evidence created",
            )
        )

        QMessageBox.information(
            self,
            self.translate(
                "workspace.evidence.created_title",
                default="Evidence created",
            ),
            self.translate(
                "workspace.evidence.created_message",
                default=(
                    "The message was added to evidence.\n\n"
                    "{title}"
                ),
                title=evidence_title,
            ),
        )

    def _execute_create_entity_action(
        self,
        *,
        case_id,
        request: InvestigationActionRequest,
    ) -> None:
        """
        Execute entity creation from a message field.
        """

        field_name = request.option(
            "field_name"
        )

        entity_type = request.option(
            "entity_type"
        )

        if not field_name or not entity_type:

            raise ValueError(
                "Entity field and type are required."
            )

        result = (
            self.container
            .workspace_controller
            .create_entity_from_message(
                case_id=case_id,
                message_data=request.payload,
                field_name=field_name,
                entity_type=entity_type,
            )
        )

        self.workspace_view.show_entities_tab()

        entity_data = (
            result.get(
                "entity",
                {},
            )
            if isinstance(
                result,
                dict,
            )
            else {}
        )

        created = bool(
            result.get(
                "created",
                False,
            )
            if isinstance(
                result,
                dict,
            )
            else False
        )

        entity_value = str(
            entity_data.get(
                "value"
            )
            or self.translate(
                "workspace.entity.default_value",
                default="Entity",
            )
        )

        if created:

            title = self.translate(
                "workspace.entity.created_title",
                default="Entity created",
            )

            message = self.translate(
                "workspace.entity.created_message",
                default=(
                    "The entity was created successfully.\n\n"
                    "{value}"
                ),
                value=entity_value,
            )

        else:

            title = self.translate(
                "workspace.entity.existing_title",
                default="Entity already exists",
            )

            message = self.translate(
                "workspace.entity.existing_message",
                default=(
                    "An identical entity already exists in this "
                    "investigation.\n\n{value}"
                ),
                value=entity_value,
            )

        QMessageBox.information(
            self,
            title,
            message,
        )

    def _execute_create_timeline_action(
        self,
        *,
        case_id,
        request: InvestigationActionRequest,
    ) -> None:
        """
        Execute timeline creation from a message.
        """

        result = (
            self.container
            .workspace_controller
            .create_timeline_from_message(
                case_id=case_id,
                message_data=request.payload,
            )
        )

        self.workspace_view.show_timeline_tab()

        timeline = (
            result.get(
                "timeline_event",
                {},
            )
            if isinstance(
                result,
                dict,
            )
            else {}
        )

        title = str(
            timeline.get(
                "title"
            )
            or "Timeline Event"
        )

        QMessageBox.information(
            self,
            self.translate(
                "workspace.timeline.created_title",
                default="Timeline updated",
            ),
            self.translate(
                "workspace.timeline.created_message",
                default=(
                    "The message was added to the timeline.\n\n"
                    "{title}"
                ),
                title=title,
            ),
        )

    def _execute_message_ai_analysis(
        self,
        *,
        case_id,
        request: InvestigationActionRequest,
    ) -> None:
        """
        Analyze one message through the configured AI provider.

        The execution service creates an AIAnalysis record. The
        surrounding dispatcher controls commit and rollback.
        """

        workspace = (
            self.container
            .workspace_controller
            .load_workspace(
                case_id
            )
        )

        if not isinstance(
            workspace,
            dict,
        ):

            raise ValueError(
                "The investigation workspace could not be loaded."
            )

        analysis = (
            self.container
            .ai_controller
            .analyze_message(
                case_id=case_id,
                workspace=workspace,
                message_data=request.payload,
            )
        )

        if not isinstance(
            analysis,
            dict,
        ):

            raise TypeError(
                "AI controller returned an invalid analysis result."
            )

        dialog = AIResultDialog(
            analysis=analysis,
            parent=self,
        )

        dialog.exec()

    # ==========================================================
    # Workspace actions
    # ==========================================================

    def _create_evidence_from_message(
        self,
        message_data: dict[str, Any],
    ) -> None:
        """
        Convert a message signal into an investigation action.
        """

        request = InvestigationActionRequest(
            action_type=(
                InvestigationActionType.CREATE_EVIDENCE
            ),
            source_type="message",
            payload=message_data,
        )

        self._dispatch_investigation_action(
            request
        )

    def _create_entity_from_message(
        self,
        message_data: dict[str, Any],
    ) -> None:
        """
        Ask the user which message field and entity type should
        be used, then dispatch the creation action.
        """

        if not isinstance(
            message_data,
            dict,
        ):

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.dialog.title",
                    default="Workspace",
                ),
                self.translate(
                    "workspace.errors.invalid_message",
                    default="Invalid message data.",
                ),
            )

            return

        field_options = [
            (
                self.translate(
                    "workspace.entity.field.sender",
                    default="Sender",
                ),
                "sender",
            ),
            (
                self.translate(
                    "workspace.entity.field.receiver",
                    default="Receiver",
                ),
                "receiver",
            ),
            (
                self.translate(
                    "workspace.entity.field.chat",
                    default="Chat",
                ),
                "chat_name",
            ),
        ]

        available_fields = [
            option
            for option in field_options
            if str(
                message_data.get(
                    option[1]
                )
                or ""
            ).strip()
        ]

        if not available_fields:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.entity.dialog_title",
                    default="Create entity",
                ),
                self.translate(
                    "workspace.entity.no_available_fields",
                    default=(
                        "This message does not contain a sender, "
                        "receiver or chat value."
                    ),
                ),
            )

            return

        field_labels = [
            label
            for label, _ in available_fields
        ]

        selected_field_label, accepted = (
            QInputDialog.getItem(
                self,
                self.translate(
                    "workspace.entity.select_field_title",
                    default="Create entity",
                ),
                self.translate(
                    "workspace.entity.select_field_prompt",
                    default=(
                        "Select which message field should become "
                        "an entity:"
                    ),
                ),
                field_labels,
                0,
                False,
            )
        )

        if not accepted:

            return

        field_name = next(
            value
            for label, value in available_fields
            if label == selected_field_label
        )

        entity_type_options = [
            (
                self.translate(
                    "workspace.entity.type.person",
                    default="Person",
                ),
                "person",
            ),
            (
                self.translate(
                    "workspace.entity.type.username",
                    default="Username",
                ),
                "username",
            ),
            (
                self.translate(
                    "workspace.entity.type.account",
                    default="Account",
                ),
                "account",
            ),
            (
                self.translate(
                    "workspace.entity.type.organization",
                    default="Organization",
                ),
                "organization",
            ),
            (
                self.translate(
                    "workspace.entity.type.other",
                    default="Other",
                ),
                "other",
            ),
        ]

        entity_type_labels = [
            label
            for label, _ in entity_type_options
        ]

        selected_type_label, accepted = (
            QInputDialog.getItem(
                self,
                self.translate(
                    "workspace.entity.select_type_title",
                    default="Create entity",
                ),
                self.translate(
                    "workspace.entity.select_type_prompt",
                    default="Select the entity type:",
                ),
                entity_type_labels,
                0,
                False,
            )
        )

        if not accepted:

            return

        entity_type = next(
            value
            for label, value in entity_type_options
            if label == selected_type_label
        )

        request = InvestigationActionRequest(
            action_type=(
                InvestigationActionType.CREATE_ENTITY
            ),
            source_type="message",
            payload=message_data,
            options={
                "field_name": field_name,
                "entity_type": entity_type,
            },
        )

        self._dispatch_investigation_action(
            request
        )

    def _create_timeline_from_message(
        self,
         message_data: dict[str, Any],
    ) -> None:
        """
        Dispatch timeline creation from a message.
        """

        request = InvestigationActionRequest(
            action_type=(
                InvestigationActionType.ADD_TIMELINE_EVENT
            ),
            source_type="message",
            payload=message_data,
        )

        self._dispatch_investigation_action(
            request
        )

    def _analyze_message_with_ai(
        self,
        message_data: dict[str, Any],
    ) -> None:
        """
        Convert a message AI request into an investigation action.
        """

        if not isinstance(
            message_data,
            dict,
        ):

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.ai.dialog_title",
                    default="AI analysis",
                ),
                self.translate(
                    "workspace.errors.invalid_message",
                    default="Invalid message data.",
                ),
            )

            return

        request = InvestigationActionRequest(
            action_type=(
                InvestigationActionType.ANALYZE_WITH_AI
            ),
            source_type="message",
            payload=message_data,
        )

        self._dispatch_investigation_action(
            request
        )

    def _ask_ai_question(
        self,
        question: str,
    ) -> None:
        """Route the existing Analyze action through the orchestrator."""

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:
            return

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.user_role",
                    default="You",
                ),
                text=normalized_question,
            )
        )

        self.workspace_view.ai_view.prompt.clear()

        self._start_orchestrated_analysis_from_ui(
            question=normalized_question,
            source="analyze_button",
        )


    def _run_ai_workflow(
        self,
        workflow_name: str,
    ) -> None:
        """Route legacy quick actions through the same orchestrator path."""

        normalized_name = str(
            workflow_name
            or ""
        ).strip()

        prompts = {
            "investigation_summary": (
                "Summarize the investigation and highlight the most "
                "important facts, relationships, chronology and uncertainties."
            ),
            "contradiction_analysis": (
                "Identify contradictions, inconsistencies and unresolved "
                "conflicts in the investigation material."
            ),
            "relationship_analysis": (
                "Analyze the most important entity relationships and graph "
                "structure in this investigation."
            ),
            "timeline_analysis": (
                "Analyze the investigation timeline, temporal patterns and "
                "important chronological changes."
            ),
            "hypothesis_generation": (
                "Generate testable investigation hypotheses grounded in the "
                "available material."
            ),
            "next_investigation_steps": (
                "Recommend lawful next investigation steps based on the "
                "available evidence and analytical gaps."
            ),
        }

        question = prompts.get(
            normalized_name,
            "Analyze this investigation.",
        )

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.user_role",
                    default="You",
                ),
                text=question,
            )
        )

        self._start_orchestrated_analysis_from_ui(
            question=question,
            source=f"quick_action:{normalized_name or 'unknown'}",
        )


    def _on_ai_question_succeeded(
        self,
        result: object,
    ) -> None:
        """
        Display a successfully generated AI response.
        """

        answer = str(
            result
            or ""
        ).strip()

        if not answer:

            answer = self.translate(
                "workspace.ai.empty_response",
                default=(
                    "The AI provider returned an empty response."
                ),
            )

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.assistant_role",
                    default="AI",
                ),
                text=answer,
            )
        )

    def _on_ai_question_failed(
        self,
        error_message: str,
    ) -> None:
        """
        Display a background AI request failure.
        """

        normalized_error = str(
            error_message
            or ""
        ).strip()

        if not normalized_error:

            normalized_error = self.translate(
                "workspace.ai.unknown_error",
                default="Unknown AI request error.",
            )

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.error_role",
                    default="Error",
                ),
                text=normalized_error,
            )
        )

        QMessageBox.critical(
            self,
            self.translate(
                "workspace.ai.dialog_title",
                default="AI assistant",
            ),
            normalized_error,
        )

    def _on_ai_thread_finished(
        self,
    ) -> None:
        """
        Restore the AI workspace after request completion.
        """

        self.workspace_view.set_ai_loading(
            False
        )

        self._ai_worker = None
        self._ai_thread = None

    def _on_ai_question_failed(
        self,
        error_message: str,
    ) -> None:
        """
        Display a background AI request failure.
        """

        normalized_error = str(
            error_message
            or ""
        ).strip()

        if not normalized_error:

            normalized_error = self.translate(
                "workspace.ai.unknown_error",
                default="Unknown AI request error.",
            )

        self.workspace_view.append_ai_message(
            self._format_ai_chat_message(
                role=self.translate(
                    "workspace.ai.error_role",
                    default="Error",
                ),
                text=normalized_error,
            )
        )

        QMessageBox.critical(
            self,
            self.translate(
                "workspace.ai.dialog_title",
                default="AI assistant",
            ),
            normalized_error,
        )

    def _on_ai_thread_finished(
        self,
    ) -> None:
        """
        Restore the AI workspace after request completion.
        """

        self.workspace_view.set_ai_loading(
            False
        )

        self._ai_worker = None

        self._ai_thread = None

    @staticmethod
    def _format_ai_chat_message(
        *,
        role: str,
        text: str,
    ) -> str:
        """
        Format one chat entry for QTextEdit.

        The AI response may contain Markdown. It is kept as plain
        readable text because QTextEdit does not render Markdown
        automatically through append().
        """

        normalized_role = str(
            role
            or ""
        ).strip()

        normalized_text = str(
            text
            or ""
        ).strip()

        return (
            f"\n{normalized_role}\n"
            f"{'─' * 48}\n"
            f"{normalized_text}\n"
        )

    def ask_about_workspace(
        self,
        *,
        case_id,
        workspace: dict,
        question: str,
    ) -> str:
        """
        Ask AI about the current investigation workspace.
        """

        if not self.can_analyze(
            case_id
        ):

            raise ValueError(
                "Investigation is not available."
            )

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "Workspace must be a dictionary."
            )

        result = (
            self.analyzer.ask_about_workspace(
                workspace=workspace,
                question=question,
            )
        )

        if not isinstance(
            result,
            dict,
        ):

            return str(
                result
            )

        return str(
            result.get(
                "response",
                "",
            )
        )


    # ==========================================================
# Face detection
# ==========================================================

    def _detect_faces(
        self,
        evidence_id: str,
    ) -> None:
        """
        Detect faces, generate SFace embeddings,
        and persist face observations in Face Memory.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            QMessageBox.warning(
                self,
                "Face detection",
                (
                    "The selected image does not contain "
                    "a valid evidence identifier."
                ),
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                "Face detection",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                "Face detection",
                (
                    "The selected investigation does not "
                    "contain an identifier."
                ),
            )

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Detecting and remembering faces...",
        )

        try:

            result = (
                self.container
                .face_analysis_service
                .analyze_and_remember(
                    evidence_id=(
                        normalized_evidence_id
                    ),
                )
            )

            self.container.commit()

            detected_count = int(
                result.get(
                    "detected_count",
                    0,
                )
                or 0
            )

            embedding_count = int(
                result.get(
                    "embedding_count",
                    0,
                )
                or 0
            )

            remembered_count = int(
                result.get(
                    "remembered_count",
                    0,
                )
                or 0
            )

            skipped_count = int(
                result.get(
                    "skipped_count",
                    0,
                )
                or 0
            )

            remembered = result.get(
                "remembered",
                [],
            )

            if not isinstance(
                remembered,
                list,
            ):

                remembered = []

            created_count = 0
            existing_count = 0

            for observation in remembered:

                if not isinstance(
                    observation,
                    dict,
                ):

                    continue

                if bool(
                    observation.get(
                        "created",
                        False,
                    )
                ):

                    created_count += 1

                else:

                    existing_count += 1

            # ------------------------------------------------------
            # Reload workspace
            # ------------------------------------------------------

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

                self.workspace_view.show_photos_tab()

            # ------------------------------------------------------
            # No faces
            # ------------------------------------------------------

            if detected_count <= 0:

                QMessageBox.information(
                    self,
                    "Face detection",
                    (
                        "Face analysis completed.\n\n"
                        "No face regions were detected."
                    ),
                )

                return

            # ------------------------------------------------------
            # Faces detected but embeddings failed
            # ------------------------------------------------------

            if embedding_count <= 0:

                QMessageBox.warning(
                    self,
                    "Face detection",
                    (
                        "Faces were detected, but no "
                        "face embeddings were generated.\n\n"
                        f"Faces detected: {detected_count}\n"
                        "SFace embeddings: 0\n"
                        "Face Memory observations: 0"
                    ),
                )

                return

            # ------------------------------------------------------
            # Result
            # ------------------------------------------------------

            message = (
                "Face analysis completed successfully.\n\n"
                f"Faces detected: {detected_count}\n"
                f"SFace embeddings: {embedding_count}\n"
                f"Face Memory observations: "
                f"{remembered_count}\n"
                f"New observations: {created_count}\n"
                f"Already remembered: {existing_count}"
            )

            if skipped_count > 0:

                message += (
                    "\n"
                    f"Skipped observations: "
                    f"{skipped_count}"
                )

            message += (
                "\n\n"
                "The detected faces are now available "
                "for similarity search in Face Memory."
            )

            QMessageBox.information(
                self,
                "Face detection",
                message,
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Face detection failed",
                (
                    "Face analysis could not "
                    "be completed.\n\n"
                    f"{exc}"
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )


    def _find_face_matches(
        self,
        evidence_id: str,
        face_id: str,
    ) -> None:
        """
        Find visually similar faces in persistent
        Face Memory for one detected face.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        normalized_face_id = str(
            face_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            QMessageBox.warning(
                self,
                "Find similar faces",
                (
                    "The selected image does not contain "
                    "a valid evidence identifier."
                ),
            )

            return

        if not normalized_face_id:

            QMessageBox.warning(
                self,
                "Find similar faces",
                "No detected face was selected.",
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                "Find similar faces",
                "No investigation selected.",
            )

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Searching Face Memory...",
        )

        try:

            # ------------------------------------------------------
            # Resolve UI face_id -> persistent FaceEmbedding
            # ------------------------------------------------------

            observations = (
                self.container
                .face_memory_service
                .get_evidence_faces(
                    normalized_evidence_id
                )
            )

            if not isinstance(
                observations,
                list,
            ):

                observations = []

            selected_observation = None

            for observation in observations:

                if not isinstance(
                    observation,
                    dict,
                ):

                    continue

                observation_face_id = str(
                    observation.get(
                        "face_id"
                    )
                    or ""
                ).strip()

                if (
                    observation_face_id
                    == normalized_face_id
                ):

                    selected_observation = (
                        observation
                    )

                    break

            if selected_observation is None:

                QMessageBox.warning(
                    self,
                    "Find similar faces",
                    (
                        "The selected face does not yet exist "
                        "in Face Memory.\n\n"
                        "Run Detect faces for this image first."
                    ),
                )

                return

            embedding_id = str(
                selected_observation.get(
                    "id"
                )
                or selected_observation.get(
                    "embedding_id"
                )
                or ""
            ).strip()

            if not embedding_id:

                raise RuntimeError(
                    "The stored face observation does not "
                    "contain an embedding identifier."
                )

            # ------------------------------------------------------
            # Vector similarity search
            # ------------------------------------------------------

            matches = (
                self.container
                .face_memory_service
                .search_observation(
                    embedding_id,
                    minimum_similarity=0.40,
                    limit=25,
                    exclude_same_evidence=True,
                    profile_only=False,
                )
            )

            if not isinstance(
                matches,
                list,
            ):

                matches = []

            # ------------------------------------------------------
            # No matches
            # ------------------------------------------------------

            if not matches:

                QMessageBox.information(
                    self,
                    "Find similar faces",
                    (
                        "No visually similar faces were found "
                        "in Face Memory.\n\n"
                        f"Selected face: "
                        f"{normalized_face_id}\n"
                        "Minimum similarity: 40%"
                    ),
                )

                return


            visuals = (
                self._prepare_face_match_visuals(
                    query_evidence_id=(
                        normalized_evidence_id
                    ),
                    matches=matches,
                )
            )

            prepared_matches = (
                visuals.get(
                    "matches",
                    [],
                )
            )

            if not isinstance(
                prepared_matches,
                list,
            ):
                prepared_matches = matches

            # ------------------------------------------------------
            # Similar Faces dialog
            # ------------------------------------------------------

            search_result = {
                "query_face": {
                    "face_id": (
                        normalized_face_id
                    ),
                    "evidence_id": (
                        normalized_evidence_id
                    ),
                    "embedding_id": (
                        embedding_id
                    ),
                    "image_path": (
                        visuals.get(
                            "query_image_path"
                        )
                    ),
                    "bbox": (
                        selected_observation.get(
                            "bbox"
                        )
                        if isinstance(
                            selected_observation,
                            dict,
                        )
                        else None
                    ),
                },
                "minimum_similarity": 0.40,
                "match_count": len(
                    prepared_matches
                ),
                "matches": prepared_matches,
            }

            dialog = SimilarFacesDialog(
                search_result=search_result,
                parent=self,
            )

            dialog.create_profile_requested.connect(
                lambda embedding_id: (
                    self._create_face_profile_from_embedding(
                        dialog=dialog,
                        embedding_id=embedding_id,
                    )
                )
            )

            dialog.assign_profile_requested.connect(
                lambda embedding_id: (
                    self._assign_face_embedding_to_profile(
                        dialog=dialog,
                        embedding_id=embedding_id,
                    )
                )
            )

            dialog.exec()

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Face similarity search failed",
                (
                    "Face Memory search could not "
                    "be completed.\n\n"
                    f"{exc}"
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )

    def _create_face_profile_from_embedding(
        self,
        *,
        dialog: SimilarFacesDialog,
        embedding_id: str,
    ) -> None:
        """
        Create a Face Memory profile and assign
        the selected observation to it.
        """

        normalized_embedding_id = str(
            embedding_id
            or ""
        ).strip()

        if not normalized_embedding_id:

            QMessageBox.warning(
                dialog,
                "Create face profile",
                "The selected face does not contain a valid embedding identifier.",
            )

            return

        label, accepted = (
            QInputDialog.getText(
                dialog,
                "Create face profile",
                "Profile name:",
            )
        )

        if not accepted:

            return

        normalized_label = str(
            label
            or ""
        ).strip()

        if not normalized_label:

            QMessageBox.warning(
                dialog,
                "Create face profile",
                "Profile name cannot be empty.",
            )

            return

        try:

            profile = (
                self.container
                .face_memory_service
                .create_profile(
                    label=normalized_label,
                )
            )

            profile_id = str(
                profile.get(
                    "id"
                )
                or ""
            ).strip()

            if not profile_id:

                raise RuntimeError(
                    "Created Face Profile does not contain an identifier."
                )

            observation = (
                self.container
                .face_memory_service
                .assign_face_to_profile(
                    normalized_embedding_id,
                    profile_id,
                )
            )

            if observation is None:

                raise LookupError(
                    "The selected Face Memory observation was not found."
                )

            self.container.commit()

            self._update_face_match_profile(
                dialog=dialog,
                embedding_id=normalized_embedding_id,
                profile=profile,
            )

            QMessageBox.information(
                dialog,
                "Face profile created",
                (
                    f'Face profile "{normalized_label}" was created '
                    "and the selected face was assigned to it."
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                dialog,
                "Create face profile failed",
                (
                    "The Face Profile could not be created.\n\n"
                    f"{exc}"
                ),
            )


    def _assign_face_embedding_to_profile(
        self,
        *,
        dialog: SimilarFacesDialog,
        embedding_id: str,
    ) -> None:
        """
        Assign the selected Face Memory observation
        to an existing Face Profile.
        """

        normalized_embedding_id = str(
            embedding_id
            or ""
        ).strip()

        if not normalized_embedding_id:

            QMessageBox.warning(
                dialog,
                "Assign face profile",
                "The selected face does not contain a valid embedding identifier.",
            )

            return

        try:

            profiles = (
                self.container
                .face_memory_service
                .list_profiles()
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                dialog,
                "Load Face Profiles failed",
                (
                    "Face Profiles could not be loaded.\n\n"
                    f"{exc}"
                ),
            )

            return

        if not profiles:

            QMessageBox.information(
                dialog,
                "Assign face profile",
                (
                    "There are no Face Profiles yet.\n\n"
                    "Create a profile first."
                ),
            )

            return

        profile_map: dict[str, dict[str, Any]] = {}

        labels: list[str] = []

        for profile in profiles:

            if not isinstance(
                profile,
                dict,
            ):

                continue

            profile_id = str(
                profile.get(
                    "id"
                )
                or ""
            ).strip()

            profile_label = str(
                profile.get(
                    "label"
                )
                or "Unnamed profile"
            ).strip()

            if not profile_id:

                continue

            display_label = (
                f"{profile_label} — {profile_id}"
            )

            labels.append(
                display_label
            )

            profile_map[
                display_label
            ] = profile

        if not labels:

            QMessageBox.information(
                dialog,
                "Assign face profile",
                "There are no available Face Profiles.",
            )

            return

        selected_label, accepted = (
            QInputDialog.getItem(
                dialog,
                "Assign to Face Profile",
                "Profile:",
                labels,
                0,
                False,
            )
        )

        if not accepted:

            return

        selected_profile = (
            profile_map.get(
                selected_label
            )
        )

        if selected_profile is None:

            return

        profile_id = str(
            selected_profile.get(
                "id"
            )
            or ""
        ).strip()

        try:

            observation = (
                self.container
                .face_memory_service
                .assign_face_to_profile(
                    normalized_embedding_id,
                    profile_id,
                )
            )

            if observation is None:

                raise LookupError(
                    "The selected Face Memory observation was not found."
                )

            self.container.commit()

            self._update_face_match_profile(
                dialog=dialog,
                embedding_id=normalized_embedding_id,
                profile=selected_profile,
            )

            profile_label = str(
                selected_profile.get(
                    "label"
                )
                or "Unnamed profile"
            )

            QMessageBox.information(
                dialog,
                "Face Profile assigned",
                (
                    "The selected face was assigned to "
                    f'"{profile_label}".'
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                dialog,
                "Assign Face Profile failed",
                (
                    "The face could not be assigned "
                    "to the selected profile.\n\n"
                    f"{exc}"
                ),
            )


    def _prepare_face_match_visuals(
        self,
        *,
        query_evidence_id: str,
        matches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Prepare image paths and bounding boxes
        for SimilarFacesDialog.

        The dialog itself must not access
        application services or repositories.
        """

        result: dict[str, Any] = {
            "query_image_path": None,
            "matches": [],
        }

        # ==========================================================
        # Query evidence
        # ==========================================================

        try:

            query_evidence = (
                self.container
                .evidence_service
                .get_evidence(
                    UUID(
                        str(
                            query_evidence_id
                        )
                    )
                )
            )

            if query_evidence is not None:

                query_file_path = getattr(
                    query_evidence,
                    "file_path",
                    None,
                )

                if query_file_path:

                    result[
                        "query_image_path"
                    ] = str(
                        query_file_path
                    )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ):

            pass

        # ==========================================================
        # Match evidence
        # ==========================================================

        for match in matches:

            if not isinstance(
                match,
                dict,
            ):

                continue

            prepared_match = dict(
                match
            )

            prepared_match[
                "image_path"
            ] = None

            embedding = match.get(
                "embedding"
            )

            if not isinstance(
                embedding,
                dict,
            ):

                result[
                    "matches"
                ].append(
                    prepared_match
                )

                continue

            evidence_id = embedding.get(
                "evidence_id"
            )

            if evidence_id is None:

                result[
                    "matches"
                ].append(
                    prepared_match
                )

                continue

            try:

                evidence = (
                    self.container
                    .evidence_service
                    .get_evidence(
                        UUID(
                            str(
                                evidence_id
                            )
                        )
                    )
                )

                if evidence is not None:

                    file_path = getattr(
                        evidence,
                        "file_path",
                        None,
                    )

                    if file_path:

                        prepared_match[
                            "image_path"
                        ] = str(
                            file_path
                        )

            except (
                TypeError,
                ValueError,
                AttributeError,
            ):

                pass

            result[
                "matches"
            ].append(
                prepared_match
            )

        return result


    # ==========================================================
    # Image analysis
    # ==========================================================

    def _calculate_image_hashes(
        self,
        evidence_id: str,
    ) -> None:
        """
        Calculate cryptographic and perceptual hashes
        for selected image evidence.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.images.hashes.title",
                    default="Image hashes",
                ),
                self.translate(
                    "workspace.images.hashes.missing_evidence",
                    default=(
                        "The selected image does not contain "
                        "a valid evidence identifier."
                    ),
                ),
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.images.hashes.title",
                    default="Image hashes",
                ),
                self.translate(
                    "workspace.errors.no_case",
                    default="No investigation selected.",
                ),
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.images.hashes.title",
                    default="Image hashes",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Calculating image hashes...",
        )

        try:

            result = (
                self.container
                .image_analysis_service
                .calculate_hashes(
                    evidence_id=(
                        normalized_evidence_id
                    ),
                )
            )

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

                self.workspace_view.show_photos_tab()

            analysis_result = result.get(
                "result",
                {}
            )

            if not isinstance(
                analysis_result,
                dict,
            ):

                analysis_result = {}

            status = str(
                analysis_result.get(
                    "status"
                )
                or "completed"
            )

            result_data = analysis_result.get(
                "data",
                {}
            )

            if not isinstance(
                result_data,
                dict,
            ):

                result_data = {}

            calculated_count = sum(
                1
                for key in (
                    "md5",
                    "sha1",
                    "sha256",
                    "sha512",
                    "average_hash",
                    "difference_hash",
                    "perceptual_hash",
                    "wavelet_hash",
                    "color_hash",
                )
                if result_data.get(
                    key
                )
            )

            QMessageBox.information(
                self,
                self.translate(
                    "workspace.images.hashes.title",
                    default="Image hashes",
                ),
                self.translate(
                    "workspace.images.hashes.completed",
                    default=(
                        "Image hashes were calculated successfully.\n\n"
                        "Status: {status}\n"
                        "Hashes calculated: {count}"
                    ),
                    status=status,
                    count=calculated_count,
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.images.hashes.failed_title",
                    default="Hash calculation failed",
                ),
                self.translate(
                    "workspace.images.hashes.failed_message",
                    default=(
                        "Image hashes could not be calculated.\n\n"
                        "{error}"
                    ),
                    error=str(
                        exc
                    ),
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )

    # ==========================================================
    # Bulk workspace actions
    # ==========================================================

    def _handle_bulk_message_action(
        self,
        action_name: str,
        messages: list,
    ) -> None:
        """
        Route a bulk action for selected messages.
        """

        normalized_action = str(
            action_name
        ).strip().lower()

        normalized_messages = [
            dict(
                message
            )
            for message in messages
            if isinstance(
                message,
                dict,
            )
        ]

        if len(
            normalized_messages
        ) < 2:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.dialog_title",
                    default="Bulk investigation",
                ),
                self.translate(
                    "workspace.bulk.not_enough_messages",
                    default=(
                        "Select at least two messages to run "
                        "a bulk action."
                    ),
                ),
            )

            return

        handlers = {
            "evidence": self._bulk_create_evidence,
            "entity": self._bulk_create_entities,
            "timeline": self._bulk_add_to_timeline,
        }

        handler = handlers.get(
            normalized_action
        )

        if handler is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.dialog_title",
                    default="Bulk investigation",
                ),
                self.translate(
                    "workspace.actions.unsupported",
                    default=(
                        "This investigation action is not "
                        "supported yet."
                    ),
                ),
            )

            return

        handler(
            normalized_messages
        )

    def _bulk_create_evidence(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Create one evidence object for every selected message.

        All records are committed together. If one creation fails,
        the complete operation is rolled back.
        """

        if self.case is None:

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.dialog_title",
                    default="Bulk investigation",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        message_count = len(
            messages
        )

        confirmation = QMessageBox.question(
            self,
            self.translate(
                "workspace.bulk.evidence.confirm_title",
                default="Create evidence",
            ),
            self.translate(
                "workspace.bulk.evidence.confirm_message",
                default=(
                    "Create evidence from {count} selected "
                    "messages?"
                ),
                count=message_count,
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            confirmation
            != QMessageBox.StandardButton.Yes
        ):

            return

        self.workspace_view.set_loading(
            True
        )

        created_count = 0

        try:

            for message_data in messages:

                (
                    self.container
                    .workspace_controller
                    .create_evidence_from_message(
                        case_id=case_id,
                        message_data=message_data,
                    )
                )

                created_count += 1

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

            self.workspace_view.show_evidence_tab()

            QMessageBox.information(
                self,
                self.translate(
                    "workspace.bulk.evidence.completed_title",
                    default="Evidence created",
                ),
                self.translate(
                    "workspace.bulk.evidence.completed_message",
                    default=(
                        "Evidence was created from "
                        "{count} messages."
                    ),
                    count=created_count,
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.bulk.evidence.failed_title",
                    default="Bulk evidence creation failed",
                ),
                self.translate(
                    "workspace.bulk.evidence.failed_message",
                    default=(
                        "No changes were saved because the bulk "
                        "operation failed.\n\n{error}"
                    ),
                    error=str(
                        exc
                    ),
                ),
            )

        finally:

            self.workspace_view.set_loading(
                False
            )

    def _bulk_create_entities(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Create or reuse entities from one selected field
        across multiple messages.
        """

        if self.case is None:

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.dialog_title",
                    default="Bulk investigation",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        field_options = [
            (
                self.translate(
                    "workspace.entity.field.sender",
                    default="Sender",
                ),
                "sender",
            ),
            (
                self.translate(
                    "workspace.entity.field.receiver",
                    default="Receiver",
                ),
                "receiver",
            ),
            (
                self.translate(
                    "workspace.entity.field.chat",
                    default="Chat",
                ),
                "chat_name",
            ),
        ]

        available_fields = [
            (
                label,
                field_name,
            )
            for label, field_name in field_options
            if any(
                str(
                    message.get(
                        field_name
                    )
                    or ""
                ).strip()
                for message in messages
            )
        ]

        if not available_fields:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.entity.title",
                    default="Create entities",
                ),
                self.translate(
                    "workspace.bulk.entity.no_fields",
                    default=(
                        "The selected messages do not contain "
                        "sender, receiver or chat values."
                    ),
                ),
            )

            return

        field_labels = [
            label
            for label, _ in available_fields
        ]

        selected_field_label, accepted = (
            QInputDialog.getItem(
                self,
                self.translate(
                    "workspace.bulk.entity.field_title",
                    default="Create entities",
                ),
                self.translate(
                    "workspace.bulk.entity.field_prompt",
                    default=(
                        "Select which message field should "
                        "be converted into entities:"
                    ),
                ),
                field_labels,
                0,
                False,
            )
        )

        if not accepted:

            return

        field_name = next(
            value
            for label, value in available_fields
            if label == selected_field_label
        )

        entity_type_options = [
            (
                self.translate(
                    "workspace.entity.type.person",
                    default="Person",
                ),
                "person",
            ),
            (
                self.translate(
                    "workspace.entity.type.username",
                    default="Username",
                ),
                "username",
            ),
            (
                self.translate(
                    "workspace.entity.type.account",
                    default="Account",
                ),
                "account",
            ),
            (
                self.translate(
                    "workspace.entity.type.organization",
                    default="Organization",
                ),
                "organization",
            ),
            (
                self.translate(
                    "workspace.entity.type.other",
                    default="Other",
                ),
                "other",
            ),
        ]

        entity_type_labels = [
            label
            for label, _ in entity_type_options
        ]

        selected_type_label, accepted = (
            QInputDialog.getItem(
                self,
                self.translate(
                    "workspace.bulk.entity.type_title",
                    default="Create entities",
                ),
                self.translate(
                    "workspace.bulk.entity.type_prompt",
                    default="Select the entity type:",
                ),
                entity_type_labels,
                0,
                False,
            )
        )

        if not accepted:

            return

        entity_type = next(
            value
            for label, value in entity_type_options
            if label == selected_type_label
        )

        usable_messages = [
            message
            for message in messages
            if str(
                message.get(
                    field_name
                )
                or ""
            ).strip()
        ]

        if not usable_messages:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.entity.title",
                    default="Create entities",
                ),
                self.translate(
                    "workspace.bulk.entity.empty_field",
                    default=(
                        "None of the selected messages contains "
                        "a value in the selected field."
                    ),
                ),
            )

            return

        confirmation = QMessageBox.question(
            self,
            self.translate(
                "workspace.bulk.entity.confirm_title",
                default="Create entities",
            ),
            self.translate(
                "workspace.bulk.entity.confirm_message",
                default=(
                    "Create or reuse entities from {count} "
                    "selected messages?"
                ),
                count=len(
                    usable_messages
                ),
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            confirmation
            != QMessageBox.StandardButton.Yes
        ):

            return

        self.workspace_view.set_loading(
            True
        )

        created_count = 0
        existing_count = 0
        skipped_count = (
            len(
                messages
            )
            - len(
                usable_messages
            )
        )

        try:

            for message_data in usable_messages:

                result = (
                    self.container
                    .workspace_controller
                    .create_entity_from_message(
                        case_id=case_id,
                        message_data=message_data,
                        field_name=field_name,
                        entity_type=entity_type,
                    )
                )

                if (
                    isinstance(
                        result,
                        dict,
                    )
                    and result.get(
                        "created",
                        False,
                    )
                ):

                    created_count += 1

                else:

                    existing_count += 1

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

            self.workspace_view.show_entities_tab()

            QMessageBox.information(
                self,
                self.translate(
                    "workspace.bulk.entity.completed_title",
                    default="Entities processed",
                ),
                self.translate(
                    "workspace.bulk.entity.completed_message",
                    default=(
                        "Bulk entity processing completed.\n\n"
                        "Created: {created}\n"
                        "Already existed: {existing}\n"
                        "Skipped: {skipped}"
                    ),
                    created=created_count,
                    existing=existing_count,
                    skipped=skipped_count,
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.bulk.entity.failed_title",
                    default="Bulk entity creation failed",
                ),
                self.translate(
                    "workspace.bulk.entity.failed_message",
                    default=(
                        "No changes were saved because the bulk "
                        "operation failed.\n\n{error}"
                    ),
                    error=str(
                        exc
                    ),
                ),
            )

        finally:

            self.workspace_view.set_loading(
                False
            )

    def _bulk_add_to_timeline(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Add selected messages to the investigation timeline.

        All timeline events are created in one transaction.
        If one event creation fails, the whole operation is rolled back.
        """

        if self.case is None:

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.dialog_title",
                    default="Bulk investigation",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        usable_messages = [
            message
            for message in messages
            if str(
                message.get(
                    "sent_at"
                )
                or ""
            ).strip()
        ]

        skipped_count = (
            len(
                messages
            )
            - len(
                usable_messages
            )
        )

        if not usable_messages:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.bulk.timeline.title",
                    default="Add to timeline",
                ),
                self.translate(
                    "workspace.bulk.timeline.no_timestamps",
                    default=(
                        "None of the selected messages contains "
                        "a timestamp."
                    ),
                ),
            )

            return

        confirmation = QMessageBox.question(
            self,
            self.translate(
                "workspace.bulk.timeline.confirm_title",
                default="Add to timeline",
            ),
            self.translate(
                "workspace.bulk.timeline.confirm_message",
                default=(
                    "Create timeline events from {count} "
                    "selected messages?"
                ),
                count=len(
                    usable_messages
                ),
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            confirmation
            != QMessageBox.StandardButton.Yes
        ):

            return

        self.workspace_view.set_loading(
            True
        )

        created_count = 0

        try:

            for message_data in usable_messages:

                (
                    self.container
                    .workspace_controller
                    .create_timeline_from_message(
                        case_id=case_id,
                        message_data=message_data,
                    )
                )

                created_count += 1

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

            self.workspace_view.show_timeline_tab()

            QMessageBox.information(
                self,
                self.translate(
                    "workspace.bulk.timeline.completed_title",
                    default="Timeline updated",
                ),
                self.translate(
                    "workspace.bulk.timeline.completed_message",
                    default=(
                        "Timeline events were created successfully.\n\n"
                        "Created: {created}\n"
                        "Skipped: {skipped}"
                    ),
                    created=created_count,
                    skipped=skipped_count,
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.bulk.timeline.failed_title",
                    default="Bulk timeline creation failed",
                ),
                self.translate(
                    "workspace.bulk.timeline.failed_message",
                    default=(
                        "No changes were saved because the bulk "
                        "operation failed.\n\n{error}"
                    ),
                    error=str(
                        exc
                    ),
                ),
            )

        finally:

            self.workspace_view.set_loading(
                False
            )

    # ==========================================================
    # Import result formatting
    # ==========================================================

    def _format_import_result(
        self,
        result: dict[str, Any] | None,
    ) -> str:
        """
        Convert import statistics into readable text.
        """

        if not result:

            return self.translate(
                "workspace.import.success_no_statistics",
                default=(
                    "Telegram export imported successfully.\n\n"
                    "The import service returned no statistics."
                ),
            )

        lines = [
            self.translate(
                "workspace.import.success",
                default=(
                    "Telegram export imported successfully."
                ),
            ),
            "",
            self.translate(
                "workspace.import.statistics",
                default="Import statistics:",
            ),
        ]

        field_labels = (
            (
                "items_found",
                "workspace.import.items_found",
                "Collected items found",
            ),
            (
                "items_created",
                "workspace.import.items_created",
                "Collected items created",
            ),
            (
                "items_imported",
                "workspace.import.items_imported",
                "Items imported",
            ),
            (
                "messages_found",
                "workspace.import.messages_found",
                "Messages found",
            ),
            (
                "messages_created",
                "workspace.import.messages_created",
                "Messages created",
            ),
            (
                "messages_skipped",
                "workspace.import.messages_skipped",
                "Messages skipped",
            ),
            (
                "entities_found",
                "workspace.import.entities_found",
                "Entities found",
            ),
            (
                "entities_created",
                "workspace.import.entities_created",
                "Entities created",
            ),
            (
                "entities_skipped",
                "workspace.import.entities_skipped",
                "Entities skipped",
            ),
            (
                "relationships_found",
                "workspace.import.relationships_found",
                "Relationships found",
            ),
            (
                "relationships_created",
                "workspace.import.relationships_created",
                "Relationships created",
            ),
            (
                "relationships_skipped",
                "workspace.import.relationships_skipped",
                "Relationships skipped",
            ),
            (
                "relationships_unresolved",
                "workspace.import.relationships_unresolved",
                "Relationships unresolved",
            ),
        )

        displayed_keys: set[str] = set()

        for (
            key,
            translation_key,
            default_label,
        ) in field_labels:

            if key not in result:

                continue

            label = self.translate(
                translation_key,
                default=default_label,
            )

            lines.append(
                f"{label}: {result[key]}"
            )

            displayed_keys.add(
                key
            )

        additional_values = {
            key: value
            for key, value in result.items()
            if key not in displayed_keys
        }

        if additional_values:

            lines.extend(
                [
                    "",
                    self.translate(
                        "workspace.import.additional_statistics",
                        default="Additional statistics:",
                    ),
                ]
            )

            for key, value in (
                additional_values.items()
            ):

                readable_key = (
                    key
                    .replace(
                        "_",
                        " ",
                    )
                    .capitalize()
                )

                lines.append(
                    f"{readable_key}: {value}"
                )

        return "\n".join(
            lines
        )

    # ==========================================================
    # Telegram import
    # ==========================================================

    def _import_telegram(
        self,
    ) -> None:
        """
        Select and import Telegram result.json.
        """

        if self.case is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.import.dialog_title",
                    default="Import",
                ),
                self.translate(
                    "workspace.import.no_case",
                    default="No investigation selected.",
                ),
            )

            return

        raw_case_id = self.case.get(
            "id"
        )

        if raw_case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.import.dialog_title",
                    default="Import",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        file_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                self.translate(
                    "workspace.import.select_file",
                    default="Select Telegram result.json",
                ),
                "",
                self.translate(
                    "workspace.import.file_filter",
                    default=(
                        "Telegram export (result.json);;"
                        "JSON files (*.json)"
                    ),
                ),
            )
        )

        if not file_path:

            return

        self.workspace_view.set_loading(
            True
        )

        try:

            case_id = UUID(
                str(
                    raw_case_id
                )
            )

            import_result = (
                self.container
                .import_controller
                .import_telegram(
                    case_id=case_id,
                    export_path=file_path,
                )
            )

            self.container.commit()

            self.load_case(
                self.case
            )

            result_message = (
                self._format_import_result(
                    import_result
                )
            )

            QMessageBox.information(
                self,
                self.translate(
                    "workspace.import.completed_title",
                    default="Import completed",
                ),
                result_message,
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.import.failed_title",
                    default="Import failed",
                ),
                str(
                    exc
                ),
            )

        finally:

            self.workspace_view.set_loading(
                False
            )

    def _import_files(
        self,
    ) -> None:
        """
        Select and import files into the active investigation.
        """

        if self.case is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.import_files.title",
                    default="Import files",
                ),
                self.translate(
                    "workspace.errors.no_case",
                    default="No investigation selected.",
                ),
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "workspace.import_files.title",
                    default="Import files",
                ),
                self.translate(
                    "workspace.errors.missing_identifier",
                    default=(
                        "The selected investigation does not "
                        "contain an identifier."
                    ),
                ),
            )

            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.translate(
                "workspace.import_files.dialog_title",
                default="Import files",
            ),
            "",
            (
                "Supported files "
                "(*.jpg *.jpeg *.png *.webp *.bmp *.gif "
                "*.tif *.tiff *.heic *.heif "
                "*.mp4 *.mkv *.mov *.avi *.webm *.m4v "
                "*.mpeg *.mpg *.wmv "
                "*.mp3 *.wav *.m4a *.aac *.ogg *.oga "
                "*.flac *.opus *.wma "
                "*.pdf *.txt *.md *.rtf *.doc *.docx "
                "*.odt *.xls *.xlsx *.ods *.ppt *.pptx "
                "*.odp *.csv *.json *.xml *.html *.htm "
                "*.eml *.zip *.rar *.7z *.tar *.gz "
                "*.bz2 *.xz);;"
                "Images "
                "(*.jpg *.jpeg *.png *.webp *.bmp *.gif "
                "*.tif *.tiff *.heic *.heif);;"
                "Video "
                "(*.mp4 *.mkv *.mov *.avi *.webm *.m4v "
                "*.mpeg *.mpg *.wmv);;"
                "Audio "
                "(*.mp3 *.wav *.m4a *.aac *.ogg *.oga "
                "*.flac *.opus *.wma);;"
                "Documents "
                "(*.pdf *.txt *.md *.rtf *.doc *.docx "
                "*.odt *.xls *.xlsx *.ods *.ppt *.pptx "
                "*.odp *.csv *.json *.xml *.html *.htm "
                "*.eml);;"
                "Archives "
                "(*.zip *.rar *.7z *.tar *.gz *.bz2 *.xz);;"
                "All files (*)"
            ),
        )

        if not file_paths:

            return

        self.workspace_view.evidence_view.set_import_enabled(
            False
        )

        try:

            result = (
                self.container
                .file_import_controller
                .import_files(
                    case_id=case_id,
                    file_paths=file_paths,
                )
            )

            if not isinstance(
                result,
                dict,
            ):

                raise ValueError(
                    "File import returned an invalid result."
                )

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

                self.workspace_view.show_evidence_tab()

            imported = int(
                result.get(
                    "imported",
                    0,
                )
                or 0
            )

            duplicates = int(
                result.get(
                    "duplicates",
                    0,
                )
                or 0
            )

            failed = int(
                result.get(
                    "failed",
                    0,
                )
                or 0
            )

            summary = self.translate(
                "workspace.import_files.result",
                default=(
                    "Imported: {imported}\n"
                    "Duplicates skipped: {duplicates}\n"
                    "Failed: {failed}"
                ),
                imported=imported,
                duplicates=duplicates,
                failed=failed,
            )

            if failed > 0:

                failed_items = []

                raw_results = result.get(
                    "results",
                    [],
                )

                if isinstance(
                    raw_results,
                    list,
                ):

                    for item in raw_results:

                        if not isinstance(
                            item,
                            dict,
                        ):

                            continue

                        if (
                            item.get(
                                "status"
                            )
                            != "failed"
                        ):

                            continue

                        source_path = str(
                            item.get(
                                "source_path"
                            )
                            or ""
                        )

                        error_message = str(
                            item.get(
                                "error"
                            )
                            or "Unknown error"
                        )

                        failed_items.append(
                            f"{source_path}\n{error_message}"
                        )

                if failed_items:

                    summary = (
                        f"{summary}\n\n"
                        + "\n\n".join(
                            failed_items
                        )
                    )

                QMessageBox.warning(
                    self,
                    self.translate(
                        "workspace.import_files.completed_title",
                        default="Import completed with errors",
                    ),
                    summary,
                )

            else:

                QMessageBox.information(
                    self,
                    self.translate(
                        "workspace.import_files.completed_title",
                        default="Import completed",
                    ),
                    summary,
                )

        except Exception as exc:

            QMessageBox.critical(
                self,
                self.translate(
                    "workspace.import_files.failed_title",
                    default="Import failed",
                ),
                str(
                    exc
                ),
            )

        finally:

            self.workspace_view.evidence_view.set_import_enabled(
                True
            )


        # ==========================================================
    # Image similarity search
    # ==========================================================

    def _find_similar_images(
        self,
        evidence_id: str,
    ) -> None:
        """
        Find visually similar images inside
        the current investigation.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            QMessageBox.warning(
                self,
                "Find similar images",
                (
                    "The selected image does not contain "
                    "a valid evidence identifier."
                ),
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                "Find similar images",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                "Find similar images",
                (
                    "The selected investigation does not "
                    "contain an identifier."
                ),
            )

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Searching for similar images...",
        )

        try:

            result = (
                self.container
                .image_similarity_search_service
                .search(
                    evidence_id=normalized_evidence_id,
                    minimum_similarity=70.0,
                    calculate_missing=True,
                )
            )

            self.container.commit()

            matches = result.get(
                "matches",
                [],
            )

            if not isinstance(
                matches,
                list,
            ):

                matches = []

            skipped = result.get(
                "skipped",
                [],
            )

            if not isinstance(
                skipped,
                list,
            ):

                skipped = []

            candidate_count = int(
                result.get(
                    "candidate_count",
                    0,
                )
                or 0
            )

            if not matches:

                QMessageBox.information(
                    self,
                    "Find similar images",
                    (
                        "No similar images were found.\n\n"
                        f"Images checked: {candidate_count}\n"
                        f"Minimum similarity: 70%"
                    ),
                )

                return

            dialog = SimilarImagesDialog(
                search_result=result,
                parent=self,
            )

            dialog.exec()

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Find similar images failed",
                (
                    "Similar image search could not "
                    "be completed.\n\n"
                    f"{exc}"
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )

    def _create_location_from_gps(
        self,
        evidence_id: str,
    ) -> None:
        """
        Create or reuse a LOCATION entity
        from GPS metadata of selected image evidence.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            QMessageBox.warning(
                self,
                "Create location from GPS",
                (
                    "The selected image does not contain "
                    "a valid evidence identifier."
                ),
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                "Create location from GPS",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                "Create location from GPS",
                (
                    "The selected investigation does not "
                    "contain an identifier."
                ),
            )

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Creating location from GPS...",
        )

        try:

            result = (
                self.container
                .image_gps_location_service
                .create_from_image(
                    normalized_evidence_id
                )
            )

            gps = result.get(
                "gps",
                {},
            )

            if not isinstance(
                gps,
                dict,
            ):

                gps = {}

            latitude = gps.get(
                "latitude"
            )

            longitude = gps.get(
                "longitude"
            )

            altitude = gps.get(
                "altitude"
            )

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

            if (
                latitude is not None
                and longitude is not None
            ):

                self.workspace_view.focus_map_location(
                    float(latitude),
                    float(longitude),
                    zoom=18,
                )

                if (
                    latitude is not None
                    and longitude is not None
                ):

                    self.workspace_view.focus_map_location(
                        float(
                            latitude
                        ),
                        float(
                            longitude
                        ),
                        zoom=18,
                    )

                self.workspace_view.focus_map_location(
                    latitude,
                    longitude,
                    zoom=18,
                )

            location = result.get(
                "location",
                {},
            )

            if not isinstance(
                location,
                dict,
            ):

                location = {}



            created = bool(
                result.get(
                    "created",
                    False,
                )
            )

            link_created = bool(
                result.get(
                    "link_created",
                    False,
                )
            )

            location_id = str(
                location.get(
                    "id"
                )
                or ""
            )

            if (
                latitude is not None
                and longitude is not None
            ):

                self.workspace_view.focus_map_location(
                    float(
                        latitude
                    ),
                    float(
                        longitude
                    ),
                    zoom=18,
                )

            if location_id:

                self.workspace_view.map_view.focus_marker(
                    location_id,
                    zoom=18,
                )

            if created:

                status_text = (
                    "A new location was created."
                )

            else:

                status_text = (
                    "An existing location was reused."
                )

            if link_created:

                link_text = (
                    "The image was linked to this location."
                )

            else:

                link_text = (
                    "The image was already linked to this location."
                )

            altitude_text = (
                str(
                    altitude
                )
                if altitude is not None
                else "Unavailable"
            )

            QMessageBox.information(
                self,
                "Location created from GPS",
                (
                    f"{status_text}\n\n"
                    f"Latitude: {latitude}\n"
                    f"Longitude: {longitude}\n"
                    f"Altitude: {altitude_text}\n\n"
                    f"{link_text}\n\n"
                    f"Location ID: {location_id}"
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Create location from GPS failed",
                (
                    "The location could not be created "
                    "from image GPS metadata.\n\n"
                    f"{exc}"
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )

    # ==========================================================
    # Image comparison
    # ==========================================================

    def _compare_images(
        self,
        evidence_id_a: str,
        evidence_id_b: str,
    ) -> None:
        """
        Compare two selected image evidence records.
        """

        first_id = str(
            evidence_id_a
            or ""
        ).strip()

        second_id = str(
            evidence_id_b
            or ""
        ).strip()

        if (
            not first_id
            or not second_id
        ):

            QMessageBox.warning(
                self,
                "Compare images",
                (
                    "Two valid images are required "
                    "for comparison."
                ),
            )

            return

        if first_id == second_id:

            QMessageBox.warning(
                self,
                "Compare images",
                (
                    "Select two different images."
                ),
            )

            return

        if self.case is None:

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            return

        self.workspace_view.photo_view.set_processing(
            True,
            "Comparing images...",
        )

        try:

            result = (
                self.container
                .image_comparison_service
                .compare(
                    evidence_id_a=first_id,
                    evidence_id_b=second_id,
                )
            )

            self.container.commit()

            comparison = result.get(
                "comparison",
                {}
            )

            if not isinstance(
                comparison,
                dict,
            ):

                comparison = {}

            similarity = comparison.get(
                "visual_similarity"
            )

            classification = str(
                comparison.get(
                    "classification"
                )
                or "unknown"
            )

            exact_match = bool(
                comparison.get(
                    "exact_match",
                    False,
                )
            )

            if similarity is None:

                similarity_text = (
                    "Unavailable"
                )

            else:

                similarity_text = (
                    f"{float(similarity):.2f}%"
                )

            perceptual = comparison.get(
                "perceptual_comparisons",
                {},
            )

            if not isinstance(
                perceptual,
                dict,
            ):

                perceptual = {}

            details: list[str] = []

            labels = {
                "perceptual_hash": "pHash",
                "difference_hash": "dHash",
                "average_hash": "aHash",
                "wavelet_hash": "wHash",
            }

            for algorithm, label in (
                labels.items()
            ):

                item = perceptual.get(
                    algorithm
                )

                if not isinstance(
                    item,
                    dict,
                ):

                    continue

                algorithm_similarity = item.get(
                    "similarity"
                )

                distance = item.get(
                    "distance"
                )

                details.append(
                    (
                        f"{label}: "
                        f"{algorithm_similarity}% "
                        f"(distance {distance})"
                    )
                )

            detail_text = (
                "\n".join(
                    details
                )
                if details
                else "No perceptual details available."
            )

            QMessageBox.information(
                self,
                "Image comparison",
                (
                    f"Visual similarity: {similarity_text}\n"
                    f"Classification: {classification}\n"
                    f"Exact file match: "
                    f"{'Yes' if exact_match else 'No'}\n\n"
                    f"{detail_text}"
                ),
            )

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

                self.workspace_view.show_photos_tab()

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Image comparison failed",
                str(
                    exc
                ),
            )

        finally:

            self.workspace_view.photo_view.set_processing(
                False
            )

    def _update_face_match_profile(
        self,
        *,
        dialog: SimilarFacesDialog,
        embedding_id: str,
        profile: dict[str, Any],
    ) -> None:
        """
        Update profile information in an already
        opened SimilarFacesDialog.
        """

        normalized_embedding_id = str(
            embedding_id
            or ""
        ).strip()

        for match in dialog.matches:

            if not isinstance(
                match,
                dict,
            ):

                continue

            embedding = match.get(
                "embedding"
            )

            if not isinstance(
                embedding,
                dict,
            ):

                continue

            current_embedding_id = str(
                embedding.get(
                    "id"
                )
                or embedding.get(
                    "embedding_id"
                )
                or ""
            ).strip()

            if (
                current_embedding_id
                != normalized_embedding_id
            ):

                continue

            match[
                "profile"
            ] = dict(
                profile
            )

            break

        dialog._load_matches()

    def _edit_location(
        self,
        location_id: str,
        marker_name: str,
        description: str,
        marker_color: str,
    ) -> None:
        """
        Update editable LOCATION properties
        and refresh the workspace map.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_location_id:

            QMessageBox.warning(
                self,
                "Edit location",
                "Location identifier is missing.",
            )

            return

        if self.case is None:

            QMessageBox.warning(
                self,
                "Edit location",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                "Edit location",
                "The investigation does not contain an identifier.",
            )

            return

        try:

            result = (
                self.container
                .image_gps_location_service
                .update_location(
                    normalized_location_id,
                    marker_name=marker_name,
                    description=description,
                    marker_color=marker_color,
                )
            )

            self.container.commit()

            workspace = (
                self.container
                .workspace_controller
                .load_workspace(
                    case_id
                )
            )

            if isinstance(
                workspace,
                dict,
            ):

                self._display_workspace(
                    workspace
                )

            self.workspace_view.show_map_tab()

            self.workspace_view.map_view.select_location(
                normalized_location_id,
                focus=True,
                zoom=18,
            )

            QMessageBox.information(
                self,
                "Location updated",
                "Location changes were saved successfully.",
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Edit location failed",
                (
                    "The location could not be updated.\n\n"
                    f"{exc}"
                ),
            )

    def _load_location_photos(
        self,
        location_id: str,
    ) -> None:
        """
        Load IMAGE Evidence connected to Location
        and send it to the map details panel.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_location_id:

            return

        try:

            photos = (
                self.container
                .image_gps_location_service
                .get_location_photos(
                    normalized_location_id
                )
            )

            self.workspace_view.set_location_photos(
                normalized_location_id,
                photos,
            )

        except Exception as exc:

            print(
                "Failed to load location photos:",
                exc,
            )

            self.workspace_view.set_location_photos(
                normalized_location_id,
                [],
            )

    def _attach_location_photo(
        self,
        location_id: str,
    ) -> None:
        """
        Attach IMAGE evidence from the current investigation
        to the selected LOCATION entity.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_location_id:

            QMessageBox.warning(
                self,
                "Attach photo",
                "No location is selected.",
            )

            return

        if not isinstance(
            self.case,
            dict,
        ):

            QMessageBox.warning(
                self,
                "Attach photo",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if not case_id:

            QMessageBox.warning(
                self,
                "Attach photo",
                (
                    "The selected investigation does not "
                    "contain an identifier."
                ),
            )

            return

        try:

            # ======================================================
            # Load evidence directly from EvidenceService
            # ======================================================

            evidences = (
                self.container
                .evidence_service
                .get_case_evidence(
                    UUID(
                        str(
                            case_id
                        )
                    )
                )
            )

            # ======================================================
            # Keep only IMAGE evidence
            # ======================================================

            image_evidences = []

            for evidence in evidences:

                evidence_type = getattr(
                    evidence,
                    "evidence_type",
                    None,
                )

                if (
                    evidence_type
                    == EvidenceType.IMAGE
                ):

                    image_evidences.append(
                        evidence
                    )

            if not image_evidences:

                QMessageBox.information(
                    self,
                    "Attach photo",
                    (
                        "There are no IMAGE evidence records "
                        "in this investigation."
                    ),
                )

                return

            # ======================================================
            # Prepare items for selection dialog
            # ======================================================

            labels = []
            evidence_by_label = {}

            for evidence in image_evidences:

                evidence_id = str(
                    getattr(
                        evidence,
                        "id",
                        "",
                    )
                    or ""
                ).strip()

                title = str(
                    getattr(
                        evidence,
                        "title",
                        "",
                    )
                    or ""
                ).strip()

                file_path = str(
                    getattr(
                        evidence,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                display_name = (
                    title
                    or file_path
                    or evidence_id
                )

                label = (
                    f"{display_name} "
                    f"[{evidence_id}]"
                )

                labels.append(
                    label
                )

                evidence_by_label[
                    label
                ] = evidence

            selected_label, accepted = (
                QInputDialog.getItem(
                    self,
                    "Attach photo",
                    "Select image evidence:",
                    labels,
                    0,
                    False,
                )
            )

            if not accepted:

                return

            selected_evidence = (
                evidence_by_label.get(
                    selected_label
                )
            )

            if selected_evidence is None:

                return

            evidence_id = getattr(
                selected_evidence,
                "id",
                None,
            )

            if evidence_id is None:

                QMessageBox.warning(
                    self,
                    "Attach photo",
                    (
                        "The selected image does not "
                        "contain an identifier."
                    ),
                )

                return

            # ======================================================
            # Link IMAGE evidence -> LOCATION entity
            # ======================================================

            result = (
                self.container
                .image_gps_location_service
                .attach_photo(
                    location_id=(
                        normalized_location_id
                    ),
                    evidence_id=(
                        str(
                            evidence_id
                        )
                    ),
                )
            )

            created = bool(
                result.get(
                    "created",
                    False,
                )
            )

            self.container.commit()

            # ======================================================
            # Refresh map/location data
            # ======================================================

            photos = (
                self.container
                .image_gps_location_service
                .get_location_photos(
                    normalized_location_id
                )
            )

            self.workspace_view.set_location_photos(
                normalized_location_id,
                photos,
            )

            if created:

                QMessageBox.information(
                    self,
                    "Attach photo",
                    (
                        "The photo has been attached "
                        "to the location."
                    ),
                )

            else:

                QMessageBox.information(
                    self,
                    "Attach photo",
                    (
                        "This photo is already attached "
                        "to the location."
                    ),
                )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Attach photo",
                (
                    "The photo could not be attached "
                    "to the location.\n\n"
                    f"{exc}"
                ),
            )

    def _attach_location_photo(
        self,
        location_id: str,
    ) -> None:
        """
        Attach one or more IMAGE evidence records
        from the current investigation to LOCATION.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        if not normalized_location_id:

            QMessageBox.warning(
                self,
                "Attach photos",
                "No location is selected.",
            )

            return

        if not isinstance(
            self.case,
            dict,
        ):

            QMessageBox.warning(
                self,
                "Attach photos",
                "No investigation selected.",
            )

            return

        case_id = self.case.get(
            "id"
        )

        if not case_id:

            QMessageBox.warning(
                self,
                "Attach photos",
                (
                    "The selected investigation does not "
                    "contain an identifier."
                ),
            )

            return

        try:

            # ======================================================
            # Load all Evidence from current case
            # ======================================================

            evidences = (
                self.container
                .evidence_service
                .get_case_evidence(
                    UUID(
                        str(
                            case_id
                        )
                    )
                )
            )

            # ======================================================
            # Keep IMAGE evidence only
            # ======================================================

            image_evidences = []

            for evidence in evidences:

                evidence_type = getattr(
                    evidence,
                    "evidence_type",
                    None,
                )

                if (
                    evidence_type
                    != EvidenceType.IMAGE
                ):

                    continue

                image_evidences.append(
                    evidence
                )

            if not image_evidences:

                QMessageBox.information(
                    self,
                    "Attach photos",
                    (
                        "There are no IMAGE evidence records "
                        "in this investigation."
                    ),
                )

                return

            # ======================================================
            # Load photos already attached to Location
            # ======================================================

            current_photos = (
                self.container
                .image_gps_location_service
                .get_location_photos(
                    normalized_location_id
                )
            )

            linked_evidence_ids = {
                str(
                    photo.get(
                        "id"
                    )
                    or ""
                ).strip()
                for photo in current_photos
                if isinstance(
                    photo,
                    dict,
                )
            }

            # ======================================================
            # Prepare available images for dialog
            # ======================================================

            available_images: list[
                dict[str, Any]
            ] = []

            for evidence in image_evidences:

                evidence_id = str(
                    getattr(
                        evidence,
                        "id",
                        "",
                    )
                    or ""
                ).strip()

                if not evidence_id:

                    continue

                if (
                    evidence_id
                    in linked_evidence_ids
                ):

                    continue

                title = str(
                    getattr(
                        evidence,
                        "title",
                        "",
                    )
                    or "Untitled image"
                ).strip()

                file_path = str(
                    getattr(
                        evidence,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                mime_type = str(
                    getattr(
                        evidence,
                        "mime_type",
                        "",
                    )
                    or ""
                ).strip()

                sha256 = str(
                    getattr(
                        evidence,
                        "sha256",
                        "",
                    )
                    or ""
                ).strip()

                metadata_json = getattr(
                    evidence,
                    "metadata_json",
                    None,
                )

                available_images.append(
                    {
                        "id": evidence_id,
                        "title": title,
                        "file_path": file_path,
                        "mime_type": mime_type,
                        "sha256": sha256,
                        "metadata_json": metadata_json,
                    }
                )

            if not available_images:

                QMessageBox.information(
                    self,
                    "Attach photos",
                    (
                        "All IMAGE evidence in this "
                        "investigation is already attached "
                        "to this location."
                    ),
                )

                return

            # ======================================================
            # Open multi-select photo dialog
            # ======================================================

            dialog = (
                SelectLocationPhotosDialog(
                    images=available_images,
                    parent=self,
                )
            )

            if (
                dialog.exec()
                != dialog.DialogCode.Accepted
            ):

                return

            selected_evidence_ids = (
                dialog.selected_evidence_ids()
            )

            if not selected_evidence_ids:

                return

            # ======================================================
            # Attach selected Evidence records
            # ======================================================

            attached_count = 0
            already_attached_count = 0

            for selected_evidence_id in (
                selected_evidence_ids
            ):

                result = (
                    self.container
                    .image_gps_location_service
                    .attach_photo(
                        location_id=(
                            normalized_location_id
                        ),
                        evidence_id=(
                            selected_evidence_id
                        ),
                    )
                )

                if result.get(
                    "created",
                    False,
                ):

                    attached_count += 1

                else:

                    already_attached_count += 1

            # ======================================================
            # Commit entire selection as one transaction
            # ======================================================

            self.container.commit()

            # ======================================================
            # Reload Location photos
            # ======================================================

            photos = (
                self.container
                .image_gps_location_service
                .get_location_photos(
                    normalized_location_id
                )
            )

            self.workspace_view.set_location_photos(
                normalized_location_id,
                photos,
            )

            # ======================================================
            # Result message
            # ======================================================

            message_parts: list[str] = []

            if attached_count:

                message_parts.append(
                    (
                        f"Attached: "
                        f"{attached_count}"
                    )
                )

            if already_attached_count:

                message_parts.append(
                    (
                        f"Already attached: "
                        f"{already_attached_count}"
                    )
                )

            QMessageBox.information(
                self,
                "Attach photos",
                (
                    "\n".join(
                        message_parts
                    )
                    or "No changes were made."
                ),
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Attach photos failed",
                (
                    "The selected photos could not "
                    "be attached to this location.\n\n"
                    f"{exc}"
                ),
            )


    def _detach_location_photo(
        self,
        location_id: str,
        evidence_id: str,
    ) -> None:
        """
        Detach selected IMAGE evidence from LOCATION.

        The original GPS source image is protected
        by ImageGpsLocationService.
        """

        normalized_location_id = str(
            location_id
            or ""
        ).strip()

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if (
            not normalized_location_id
            or not normalized_evidence_id
        ):

            return

        answer = QMessageBox.question(
            self,
            "Remove photo",
            (
                "Remove this photo from the location?\n\n"
                "The image itself will remain in the investigation."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):

            return

        try:

            removed = (
                self.container
                .image_gps_location_service
                .detach_photo(
                    location_id=(
                        normalized_location_id
                    ),
                    evidence_id=(
                        normalized_evidence_id
                    ),
                )
            )

            if not removed:

                QMessageBox.information(
                    self,
                    "Remove photo",
                    (
                        "This photo is not attached "
                        "to the selected location."
                    ),
                )

                return

            self.container.commit()

            photos = (
                self.container
                .image_gps_location_service
                .get_location_photos(
                    normalized_location_id
                )
            )

            self.workspace_view.set_location_photos(
                normalized_location_id,
                photos,
            )

        except Exception as exc:

            self.container.rollback()

            QMessageBox.critical(
                self,
                "Remove photo failed",
                (
                    "The photo could not be removed "
                    "from this location.\n\n"
                    f"{exc}"
                ),
            )


    def _open_location_photo(
        self,
        evidence_id: str,
    ) -> None:
        """
        Open IMAGE evidence from the map
        in the Photos workspace.
        """

        normalized_evidence_id = str(
            evidence_id
            or ""
        ).strip()

        if not normalized_evidence_id:

            return

        try:

            self.workspace_view.tabs.setCurrentIndex(
                self.workspace_view.photos_tab_index
            )

            selected = (
                self.workspace_view
                .photo_view
                .select_image(
                    normalized_evidence_id
                )
            )

            if not selected:

                QMessageBox.warning(
                    self,
                    "Open photo",
                    (
                        "The selected image could not be found "
                        "in the current Photos workspace."
                    ),
                )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Open photo failed",
                (
                    "The image could not be opened "
                    "in the Photos workspace.\n\n"
                    f"{exc}"
                ),
            )