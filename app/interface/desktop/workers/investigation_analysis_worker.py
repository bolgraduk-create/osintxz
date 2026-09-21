from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.investigation_analysis_contracts import (
    InvestigationAnalysisProgressEvent,
    InvestigationAnalysisResult,
)


class InvestigationAnalysisWorker(QObject):
    """Thread-owned adapter over the canonical analysis runner."""

    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        case_id: str,
        question: str = "",
    ) -> None:
        super().__init__()
        self.case_id = str(case_id or "").strip()
        self.question = str(question or "").strip()

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            if not self.case_id:
                raise ValueError(
                    "Select an investigation before running analysis."
                )

            UUID(self.case_id)
            session = create_session()
            container = ServiceContainer(session)

            result = container.investigation_analysis_runner.run(
                self.case_id,
                question=self.question or None,
                progress_callback=self._on_progress,
                metadata={
                    "source": "desktop_analysis_workspace",
                    "ui": "qml",
                },
            )

            snapshot = self._snapshot_result(
                result=result,
                container=container,
                question=self.question,
            )

            # The orchestrator/RAG pipeline is read-only. Close any transaction
            # implicitly opened by repositories instead of committing.
            container.rollback()

            self.succeeded.emit(
                {
                    "snapshot": snapshot,
                    "duration": perf_counter() - started,
                }
            )
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass

            self.failed.emit(
                {
                    "error": str(exc),
                    "duration": perf_counter() - started,
                    "caseId": self.case_id,
                }
            )
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass

    def _on_progress(
        self,
        event: InvestigationAnalysisProgressEvent,
    ) -> None:
        self.progress.emit(
            {
                "eventType": event.event_type.value,
                "stage": (
                    event.stage.value
                    if event.stage is not None
                    else ""
                ),
                "stageStatus": (
                    event.stage_status.value
                    if event.stage_status is not None
                    else ""
                ),
                "stageIndex": int(event.stage_index),
                "stageCount": int(event.stage_count),
                "progress": round(event.progress_fraction(), 4),
                "message": str(event.message or ""),
            }
        )

    @classmethod
    def _snapshot_result(
        cls,
        *,
        result: InvestigationAnalysisResult,
        container: Any,
        question: str,
    ) -> dict[str, Any]:
        stages = [
            {
                "stage": item.stage.value,
                "label": cls._stage_label(item.stage.value),
                "status": item.status.value,
                "durationSeconds": round(
                    float(item.duration_seconds or 0.0),
                    3,
                ),
                "warnings": list(item.warnings),
                "error": (
                    {
                        "type": item.error.error_type,
                        "message": item.error.message,
                    }
                    if item.error is not None
                    else {}
                ),
            }
            for item in result.stage_results
        ]

        summary_text = ""
        summary_refs: list[str] = []
        conclusions: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        model_info: dict[str, Any] = {}
        citation_summary = {
            "valid": 0,
            "invalid": 0,
            "unresolved": 0,
        }
        sections: list[str] = []
        generated_at = ""

        unified = result.unified_context
        if unified is not None:
            sections = list(unified.available_sections)
            generated = getattr(unified, "generated_at", None)
            generated_at = (
                generated.isoformat()
                if hasattr(generated, "isoformat")
                else str(generated or "")
            )

            rag = unified.rag
            rag_summary = rag.summary
            if rag_summary is not None:
                summary_text = str(rag_summary.summary or "")
                summary_refs = list(
                    rag_summary.source_references or ()
                )
                model_info = dict(
                    rag_summary.model_info or {}
                )

            rag_conclusions = rag.conclusions
            if rag_conclusions is not None:
                if not model_info:
                    model_info = dict(
                        rag_conclusions.model_info or {}
                    )
                for item in rag_conclusions.conclusions:
                    kind = item.kind.value
                    conclusions.append(
                        {
                            "kind": kind,
                            "label": cls._conclusion_label(kind),
                            "text": str(item.text or ""),
                            "sourceReferences": list(
                                item.source_references or ()
                            ),
                            "workflow": str(
                                item.workflow_name or ""
                            ),
                        }
                    )

            rag_context = rag.context
            if rag_context is not None:
                for source in rag_context.included_sources:
                    sources.append(
                        {
                            "reference": str(
                                source.reference_id or ""
                            ),
                            "title": str(source.title or ""),
                            "objectType": str(
                                source.object_type or ""
                            ),
                            "objectId": str(
                                source.object_id or ""
                            ),
                            "score": round(
                                float(source.final_score or 0.0),
                                4,
                            ),
                            "status": str(source.status or ""),
                            "matchedMethods": list(
                                source.matched_methods or ()
                            ),
                        }
                    )

            citation_validation = rag.summary_citations
            if citation_validation is not None:
                citation_summary = {
                    "valid": int(
                        citation_validation.valid_count
                    ),
                    "invalid": int(
                        len(citation_validation.invalid_citations)
                    ),
                    "unresolved": int(
                        len(citation_validation.unresolved_citations)
                    ),
                }

        provider_metadata = dict(
            container.ai_manager.metadata() or {}
        )
        if not model_info:
            model_info = dict(
                container.ai_manager.info() or {}
            )

        all_refs: list[str] = []
        seen_refs: set[str] = set()
        for ref in summary_refs:
            if ref not in seen_refs:
                seen_refs.add(ref)
                all_refs.append(ref)
        for conclusion in conclusions:
            for ref in conclusion["sourceReferences"]:
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    all_refs.append(ref)

        return {
            "caseId": str(result.case_id),
            "status": result.status.value,
            "question": question,
            "durationSeconds": round(
                float(result.duration_seconds or 0.0),
                3,
            ),
            "warnings": list(result.warnings),
            "stages": stages,
            "successfulStages": result.successful_stage_count(),
            "failedStages": result.failed_stage_count(),
            "skippedStages": result.skipped_stage_count(),
            "cancelledStages": result.cancelled_stage_count(),
            "sections": sections,
            "generatedAt": generated_at,
            "summary": summary_text,
            "summarySourceReferences": summary_refs,
            "conclusions": conclusions,
            "sources": sources,
            "citedSourceReferences": all_refs,
            "citationSummary": citation_summary,
            "modelInfo": model_info,
            "provider": provider_metadata,
            "notice": (
                "AI-generated analysis is analytical assistance, not Evidence "
                "and not an independently verified fact. R-style references "
                "only show which bounded investigation sources were available."
            ),
        }

    @staticmethod
    def _stage_label(value: str) -> str:
        return str(value or "").replace("_", " ").title()

    @staticmethod
    def _conclusion_label(value: str) -> str:
        labels = {
            "hypotheses": "Hypotheses",
            "contradictions": "Contradictions",
            "next_steps": "Next Investigation Steps",
        }
        return labels.get(
            str(value or ""),
            str(value or "").replace("_", " ").title(),
        )
