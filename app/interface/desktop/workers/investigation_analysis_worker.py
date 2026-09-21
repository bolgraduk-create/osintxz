from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.analysis_history_service import AnalysisHistoryService
from app.application.analysis_run_profile import (
    estimate_openai_cost,
    normalize_analysis_mode,
    normalize_openai_model,
    normalize_reasoning_effort,
)
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
        mode: str = "standard",
        model: str = "",
        reasoning_effort: str = "",
        scope_type: str = "case",
        focus_entity_id: str = "",
        focus_entity_label: str = "",
    ) -> None:
        super().__init__()
        self.case_id = str(case_id or "").strip()
        self.question = str(question or "").strip()
        self.mode = str(mode or "standard").strip().casefold()
        self.model = str(model or "").strip()
        self.reasoning_effort = str(reasoning_effort or "").strip().casefold()
        self.scope_type = str(scope_type or "case").strip().casefold()
        self.focus_entity_id = str(focus_entity_id or "").strip()
        self.focus_entity_label = str(focus_entity_label or "").strip()

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

            profile = normalize_analysis_mode(self.mode)
            provider_name = str(
                container.ai_manager.provider_name or ""
            ).strip().casefold()

            selected_model = self.model
            if provider_name == "openai":
                selected_model = normalize_openai_model(
                    selected_model,
                    fallback=profile.recommended_model,
                )
            elif not selected_model:
                selected_model = str(
                    container.ai_manager.model_name or ""
                ).strip()

            selected_reasoning = normalize_reasoning_effort(
                self.reasoning_effort,
                fallback=profile.recommended_reasoning,
            )

            scope_type = (
                "person"
                if (
                    self.scope_type == "person"
                    and self.focus_entity_id
                    and self.focus_entity_label
                )
                else "case"
            )
            scope = {
                "type": scope_type,
                "entityId": (
                    self.focus_entity_id
                    if scope_type == "person"
                    else ""
                ),
                "label": (
                    self.focus_entity_label
                    if scope_type == "person"
                    else "Entire Investigation"
                ),
            }
            run_config = {
                "mode": profile.key,
                "modeLabel": profile.label,
                "model": selected_model,
                "reasoningEffort": selected_reasoning,
                "plannedAiRequests": profile.ai_request_count,
                "maxOutputTokensPerRequest": profile.max_output_tokens,
                "provider": provider_name,
            }

            result = container.investigation_analysis_runner.run(
                self.case_id,
                question=self.question or None,
                progress_callback=self._on_progress,
                metadata={
                    "source": "desktop_analysis_workspace",
                    "ui": "qml",
                    "analysis_mode": profile.key,
                    "ai_provider": provider_name,
                    "ai_model": selected_model,
                    "reasoning_effort": selected_reasoning,
                    "scope_type": scope_type,
                    "focus_entity_id": scope["entityId"],
                    "focus_entity_label": scope["label"],
                },
            )

            usage = dict(
                container.ai_manager.usage_snapshot() or {}
            )
            cost = (
                estimate_openai_cost(usage)
                if provider_name == "openai"
                else {
                    "currency": "",
                    "estimatedUsd": 0.0,
                    "display": "Local",
                    "pricedRequests": 0,
                    "unpricedRequests": 0,
                    "pricingEffectiveDate": "",
                    "approximate": False,
                    "notice": "Local provider usage is not billed by OpenAI.",
                }
            )

            snapshot = self._snapshot_result(
                result=result,
                container=container,
                question=self.question,
                run_config=run_config,
                scope=scope,
                usage=usage,
                cost=cost,
            )

            # The analytical pipeline itself remains read-only.
            container.rollback()

            # Analysis history is an explicit AIAnalysis artifact, never
            # Evidence. Use an isolated short transaction so the analysis
            # runner's read-only transaction boundary remains unchanged.
            history_session = None
            try:
                history_session = create_session()
                history_service = AnalysisHistoryService(history_session)
                history_id = history_service.save(
                    case_id=self.case_id,
                    snapshot=snapshot,
                )
                history_session.commit()
                snapshot["historyId"] = history_id
                snapshot["historyPersisted"] = True
            except Exception as history_exc:
                if history_session is not None:
                    try:
                        history_session.rollback()
                    except Exception:
                        pass
                snapshot["historyPersisted"] = False
                warnings = list(snapshot.get("warnings") or [])
                warnings.append(
                    "Analysis completed, but history could not be saved: "
                    + str(history_exc)
                )
                snapshot["warnings"] = warnings
            finally:
                if history_session is not None:
                    try:
                        history_session.close()
                    except Exception:
                        pass

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
        run_config: dict[str, Any] | None = None,
        scope: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        cost: dict[str, Any] | None = None,
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
        facts: list[dict[str, Any]] = []
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
                            "epistemicClass": (
                                "hypothesis"
                                if kind == "hypotheses"
                                else (
                                    "conflict"
                                    if kind == "contradictions"
                                    else "recommendation"
                                )
                            ),
                            "verifiedFact": False,
                        }
                    )

            rag_context = rag.context
            if rag_context is not None:
                for source in rag_context.included_sources:
                    source_text = " ".join(
                        str(source.text or "").split()
                    )
                    source_row = {
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
                        "snippet": source_text[:900],
                    }
                    sources.append(source_row)
                    facts.append(
                        {
                            "reference": source_row["reference"],
                            "title": source_row["title"],
                            "text": source_text[:650],
                            "objectType": source_row["objectType"],
                            "objectId": source_row["objectId"],
                            "status": "source_backed",
                            "verifiedFact": False,
                            "notice": (
                                "Direct source material selected by RAG; "
                                "not automatically independently verified."
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

        normalized_run_config = dict(run_config or {})
        if normalized_run_config.get("model"):
            model_info["model"] = normalized_run_config["model"]
        if normalized_run_config.get("reasoningEffort"):
            model_info["reasoning_effort"] = (
                normalized_run_config["reasoningEffort"]
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

        conclusion_map = {
            "hypotheses": [],
            "contradictions": [],
            "next_steps": [],
        }
        for conclusion in conclusions:
            kind = str(conclusion.get("kind") or "")
            if kind in conclusion_map:
                conclusion_map[kind].append(conclusion)

        return {
            "caseId": str(result.case_id),
            "status": result.status.value,
            "question": question,
            "scope": dict(
                scope
                or {
                    "type": "case",
                    "entityId": "",
                    "label": "Entire Investigation",
                }
            ),
            "runConfig": normalized_run_config,
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
            "conclusionMap": conclusion_map,
            "facts": facts,
            "sources": sources,
            "citedSourceReferences": all_refs,
            "citationSummary": citation_summary,
            "modelInfo": model_info,
            "provider": provider_metadata,
            "usage": dict(usage or {}),
            "cost": dict(cost or {}),
            "notice": (
                "AI-generated analysis is analytical assistance, not Evidence "
                "and not an independently verified fact. Facts shown here are "
                "source-backed observations from bounded RAG context; R-style "
                "references are provenance markers, not truth certification."
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
