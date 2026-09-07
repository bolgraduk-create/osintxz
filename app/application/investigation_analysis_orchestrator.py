"""
Application-level orchestration for investigation analysis.

The orchestrator coordinates already existing production analysis
services. It does not implement mathematical algorithms, retrieval,
AI generation, persistence or UI behavior.

Current integration state:
- orchestration engine: connected
- case validation: connected
- graph analysis: connected
- temporal analysis: connected
- anomaly analysis: connected with precomputed Graph/Temporal reuse
- entity clustering: connected with precomputed Graph/Temporal reuse
- shared Entity feature extraction is reused from Anomaly when available
- multimodal analysis: connected as read-only evidence bridge
- RAG retrieval: connected once through InvestigationRAGRetrievalService
  over UnifiedSearchService
- remaining AI/RAG stage handlers are connected incrementally before
  desktop integration
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any
from uuid import UUID


from app.application.investigation_analysis_contracts import (
    CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER,
    DEFAULT_INVESTIGATION_ANALYSIS_STAGES,
    INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES,
    InvestigationAnalysisCancellationToken,
    InvestigationAnalysisProgressCallback,
    InvestigationAnalysisProgressEvent,
    InvestigationAnalysisProgressEventType,
    InvestigationAnalysisRequest,
    InvestigationAnalysisResult,
    InvestigationAnalysisStage,
    InvestigationAnalysisStageError,
    InvestigationAnalysisStageResult,
    InvestigationAnalysisStageStatus,
    InvestigationAnalysisStatus,
)
from app.application.investigation_anomaly_analysis_service import (
    InvestigationAnomalyAnalysisService,
)
from app.application.investigation_entity_clustering_service import (
    InvestigationEntityClusteringService,
)

from app.application.investigation_entity_resolution_analysis_service import (
    InvestigationEntityResolutionAnalysisService,
)

from app.application.investigation_evidence_analysis_service import (
    InvestigationEvidenceAnalysisService,
)
from app.application.investigation_graph_analysis_service import (
    InvestigationGraphAnalysisService,
)
from app.application.investigation_multimodal_analysis_service import (
    InvestigationMultimodalAnalysisResult,
    InvestigationMultimodalAnalysisService,
)
from app.application.investigation_temporal_analysis_service import (
    InvestigationTemporalAnalysisService,
)
from app.services.case_service import (
    CaseService,
)
from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalResult,
    InvestigationRAGRetrievalService,
)
from app.services.investigation_rag_context_builder import (
    InvestigationRAGContext,
    InvestigationRAGContextBuilder,
)
from app.services.investigation_rag_summary_service import (
    InvestigationRAGSummaryResult,
    InvestigationRAGSummaryService,
)
from app.services.investigation_rag_conclusions_service import (
    InvestigationRAGConclusionsResult,
    InvestigationRAGConclusionsService,
)
from app.services.investigation_rag_grounded_citation_service import (
    InvestigationRAGCitationValidation,
    InvestigationRAGConclusionsCitationValidation,
    InvestigationRAGGroundedCitationService,
)
from app.services.investigation_unified_analytical_context_service import (
    InvestigationUnifiedAnalyticalContextService,
)


logger = logging.getLogger(
    __name__
)


StageHandler = Callable[
    [
        UUID,
        InvestigationAnalysisRequest,
        dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        dict[str, object],
    ],
    object | None,
]


class InvestigationAnalysisOrchestrator:
    """
    Coordinate one complete investigation analysis run.

    Architectural boundaries:
    - no Qt dependencies
    - no ORM writes
    - no direct AI-provider access
    - no mathematical algorithms
    - no hidden stage caching
    """

    VERSION = "1"

    def __init__(
        self,
        *,
        case_service: CaseService,
        investigation_entity_resolution_analysis_service: (
            InvestigationEntityResolutionAnalysisService
        ),
        investigation_evidence_analysis_service: (
            InvestigationEvidenceAnalysisService
        ),
        investigation_graph_analysis_service: (
            InvestigationGraphAnalysisService
        ),
        investigation_temporal_analysis_service: (
            InvestigationTemporalAnalysisService
        ),
        investigation_anomaly_analysis_service: (
            InvestigationAnomalyAnalysisService
        ),
        investigation_entity_clustering_service: (
            InvestigationEntityClusteringService
        ),
        investigation_multimodal_analysis_service: (
            InvestigationMultimodalAnalysisService
        ),
        investigation_rag_retrieval_service: (
            InvestigationRAGRetrievalService
        ),
        investigation_rag_context_builder: (
            InvestigationRAGContextBuilder
        ),
        investigation_rag_summary_service: (
            InvestigationRAGSummaryService
        ),
        investigation_rag_conclusions_service: (
            InvestigationRAGConclusionsService
        ),
        investigation_rag_grounded_citation_service: (
            InvestigationRAGGroundedCitationService
        ),
        investigation_unified_analytical_context_service: (
            InvestigationUnifiedAnalyticalContextService
        ),
    ) -> None:

        self.case_service = (
            case_service
        )

        self.investigation_entity_resolution_analysis_service = (
            investigation_entity_resolution_analysis_service
        )

        self.investigation_evidence_analysis_service = (
            investigation_evidence_analysis_service
        )

        self.investigation_graph_analysis_service = (
            investigation_graph_analysis_service
        )

        self.investigation_temporal_analysis_service = (
            investigation_temporal_analysis_service
        )

        self.investigation_anomaly_analysis_service = (
            investigation_anomaly_analysis_service
        )

        self.investigation_entity_clustering_service = (
            investigation_entity_clustering_service
        )

        self.investigation_multimodal_analysis_service = (
            investigation_multimodal_analysis_service
        )

        self.investigation_rag_retrieval_service = (
            investigation_rag_retrieval_service
        )

        self.investigation_rag_context_builder = (
            investigation_rag_context_builder
        )

        self.investigation_rag_summary_service = (
            investigation_rag_summary_service
        )

        self.investigation_rag_conclusions_service = (
            investigation_rag_conclusions_service
        )

        self.investigation_rag_grounded_citation_service = (
            investigation_rag_grounded_citation_service
        )

        self.investigation_unified_analytical_context_service = (
            investigation_unified_analytical_context_service
        )

        self._stage_handlers: dict[
            InvestigationAnalysisStage,
            StageHandler,
        ] = {
            InvestigationAnalysisStage.CASE_VALIDATION: (
                self._run_case_validation
            ),
            InvestigationAnalysisStage.ENTITY_RESOLUTION: (
                self._run_entity_resolution_analysis
            ),
            InvestigationAnalysisStage.EVIDENCE: (
                self._run_evidence_analysis
            ),
            InvestigationAnalysisStage.GRAPH: (
                self._run_graph_analysis
            ),
            InvestigationAnalysisStage.TEMPORAL: (
                self._run_temporal_analysis
            ),
            InvestigationAnalysisStage.ANOMALY: (
                self._run_anomaly_analysis
            ),
            InvestigationAnalysisStage.CLUSTERING: (
                self._run_entity_clustering
            ),
            InvestigationAnalysisStage.MULTIMODAL: (
                self._run_multimodal_analysis
            ),
            InvestigationAnalysisStage.RAG: (
                self._run_rag_retrieval
            ),
            InvestigationAnalysisStage.UNIFIED_CONTEXT: (
                self._run_unified_context
            ),
        }

    # ======================================================
    # Public API
    # ======================================================

    def analyze(
        self,
        request: InvestigationAnalysisRequest,
        *,
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ) = None,
        cancellation_token: (
            InvestigationAnalysisCancellationToken
            | None
        ) = None,
    ) -> InvestigationAnalysisResult:
        """
        Execute one normalized investigation analysis plan.

        A strict preflight check currently prevents incomplete
        integration from silently producing misleading results.
        Once all planned handlers are connected, the same execution
        engine runs the full production pipeline.
        """

        if not isinstance(
            request,
            InvestigationAnalysisRequest,
        ):

            raise TypeError(
                "request must be "
                "InvestigationAnalysisRequest."
            )

        started_at = perf_counter()

        normalized_request = (
            self.normalize_request(
                request
            )
        )

        case_id = normalized_request.case_id

        if not isinstance(
            case_id,
            UUID,
        ):

            raise RuntimeError(
                "Normalized analysis request "
                "must contain UUID case_id."
            )

        execution_plan = (
            self.build_execution_plan(
                normalized_request
            )
        )

        self._ensure_execution_ready(
            execution_plan
        )

        stage_results: list[
            InvestigationAnalysisStageResult
        ] = []

        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ] = {}

        # Explicit per-run artifacts that are not standalone stages.
        # They exist only for this analyze() invocation and are passed
        # to handlers explicitly; no hidden cross-run cache is used.
        run_artifacts: dict[str, object] = {}

        global_warnings: list[str] = []

        cancelled = False

        self._emit_progress(
            progress_callback,
            InvestigationAnalysisProgressEvent(
                case_id=case_id,
                event_type=(
                    InvestigationAnalysisProgressEventType
                    .ANALYSIS_STARTED
                ),
                stage_index=0,
                stage_count=len(
                    execution_plan
                ),
                message=(
                    "Starting investigation analysis."
                ),
            ),
        )

        for plan_index, stage in enumerate(
            execution_plan,
            start=1,
        ):

            if self._is_cancelled(
                cancellation_token
            ):

                cancelled = True

                self._append_cancelled_stages(
                    case_id=case_id,
                    execution_plan=execution_plan,
                    starting_index=plan_index - 1,
                    stage_results=stage_results,
                    stage_result_map=stage_result_map,
                    progress_callback=(
                        progress_callback
                    ),
                )

                break

            dependency_warning = (
                self._get_dependency_skip_warning(
                    stage=stage,
                    stage_result_map=(
                        stage_result_map
                    ),
                )
            )

            if dependency_warning:

                stage_result = (
                    InvestigationAnalysisStageResult(
                        stage=stage,
                        status=(
                            InvestigationAnalysisStageStatus
                            .SKIPPED
                        ),
                        warnings=(
                            dependency_warning,
                        ),
                    )
                )

                stage_results.append(
                    stage_result
                )

                stage_result_map[
                    stage
                ] = stage_result

                self._emit_stage_finished(
                    case_id=case_id,
                    stage=stage,
                    stage_result=stage_result,
                    stage_index=plan_index,
                    stage_count=len(
                        execution_plan
                    ),
                    progress_callback=(
                        progress_callback
                    ),
                )

                continue

            self._emit_progress(
                progress_callback,
                InvestigationAnalysisProgressEvent(
                    case_id=case_id,
                    event_type=(
                        InvestigationAnalysisProgressEventType
                        .STAGE_STARTED
                    ),
                    stage=stage,
                    stage_index=plan_index,
                    stage_count=len(
                        execution_plan
                    ),
                    message=(
                        self._stage_started_message(
                            stage
                        )
                    ),
                ),
            )

            stage_started_at = (
                perf_counter()
            )

            try:

                handler = (
                    self._stage_handlers[
                        stage
                    ]
                )

                stage_value = handler(
                    case_id,
                    normalized_request,
                    stage_result_map,
                    run_artifacts,
                )

                stage_result = (
                    InvestigationAnalysisStageResult(
                        stage=stage,
                        status=(
                            InvestigationAnalysisStageStatus
                            .SUCCESS
                        ),
                        duration_seconds=(
                            perf_counter()
                            - stage_started_at
                        ),
                        result=stage_value,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Investigation analysis stage "
                    "failed: case_id=%s stage=%s",
                    case_id,
                    stage.value,
                )

                stage_result = (
                    InvestigationAnalysisStageResult(
                        stage=stage,
                        status=(
                            InvestigationAnalysisStageStatus
                            .FAILED
                        ),
                        duration_seconds=(
                            perf_counter()
                            - stage_started_at
                        ),
                        error=(
                            InvestigationAnalysisStageError(
                                error_type=(
                                    type(
                                        exc
                                    ).__name__
                                ),
                                message=(
                                    str(
                                        exc
                                    ).strip()
                                    or (
                                        "Unknown stage "
                                        "execution error."
                                    )
                                ),
                            )
                        ),
                    )
                )

            stage_results.append(
                stage_result
            )

            stage_result_map[
                stage
            ] = stage_result

            self._emit_stage_finished(
                case_id=case_id,
                stage=stage,
                stage_result=stage_result,
                stage_index=plan_index,
                stage_count=len(
                    execution_plan
                ),
                progress_callback=(
                    progress_callback
                ),
            )

            if (
                stage
                == InvestigationAnalysisStage.CASE_VALIDATION
                and stage_result.status
                == InvestigationAnalysisStageStatus.FAILED
            ):

                warning = (
                    "Analysis stopped because "
                    "case validation failed."
                )

                global_warnings.append(
                    warning
                )

                self._append_skipped_stages(
                    case_id=case_id,
                    execution_plan=execution_plan,
                    starting_index=plan_index,
                    reason=(
                        "Skipped because case "
                        "validation failed."
                    ),
                    stage_results=stage_results,
                    stage_result_map=(
                        stage_result_map
                    ),
                    progress_callback=(
                        progress_callback
                    ),
                )

                break

        result_status = (
            self._determine_status(
                stage_results=tuple(
                    stage_results
                ),
                cancelled=cancelled,
            )
        )

        unified_context = (
            self._extract_unified_context(
                stage_result_map
            )
        )

        duration_seconds = (
            perf_counter()
            - started_at
        )

        result = (
            InvestigationAnalysisResult(
                case_id=case_id,
                status=result_status,
                stage_results=tuple(
                    stage_results
                ),
                unified_context=(
                    unified_context
                ),
                duration_seconds=(
                    duration_seconds
                ),
                warnings=tuple(
                    global_warnings
                ),
                metadata={
                    "orchestrator_version": (
                        self.VERSION
                    ),
                    "requested_stage_count": (
                        len(
                            execution_plan
                        )
                    ),
                    "executed_stage_count": (
                        len(
                            stage_results
                        )
                    ),
                    "analysis_recomputed": True,
                },
            )
        )

        self._emit_progress(
            progress_callback,
            InvestigationAnalysisProgressEvent(
                case_id=case_id,
                event_type=(
                    InvestigationAnalysisProgressEventType
                    .ANALYSIS_FINISHED
                ),
                stage_index=len(
                    execution_plan
                ),
                stage_count=len(
                    execution_plan
                ),
                message=(
                    self._analysis_finished_message(
                        result.status
                    )
                ),
            ),
        )

        return result

    def normalize_request(
        self,
        request: InvestigationAnalysisRequest,
    ) -> InvestigationAnalysisRequest:
        """
        Return a request with canonical UUID case_id.
        """

        if not isinstance(
            request,
            InvestigationAnalysisRequest,
        ):

            raise TypeError(
                "request must be "
                "InvestigationAnalysisRequest."
            )

        case_id = self.normalize_case_id(
            request.case_id
        )

        return InvestigationAnalysisRequest(
            case_id=case_id,
            question=request.question,
            requested_stages=(
                request.requested_stages
            ),
            metadata=request.metadata,
        )

    @staticmethod
    def normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:
        """
        Normalize a case identifier to UUID.
        """

        if isinstance(
            case_id,
            UUID,
        ):

            return case_id

        normalized = str(
            case_id
            or ""
        ).strip()

        if not normalized:

            raise ValueError(
                "case_id cannot be empty."
            )

        try:

            return UUID(
                normalized
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:

            raise ValueError(
                "case_id must contain a valid UUID."
            ) from exc

    def build_execution_plan(
        self,
        request: InvestigationAnalysisRequest,
    ) -> tuple[
        InvestigationAnalysisStage,
        ...,
    ]:
        """
        Build deterministic stage plan with dependency expansion.
        """

        if not isinstance(
            request,
            InvestigationAnalysisRequest,
        ):

            raise TypeError(
                "request must be "
                "InvestigationAnalysisRequest."
            )

        requested = (
            DEFAULT_INVESTIGATION_ANALYSIS_STAGES
            if request.requested_stages is None
            else request.requested_stages
        )

        selected: set[
            InvestigationAnalysisStage
        ] = set(
            requested
        )

        selected.add(
            InvestigationAnalysisStage
            .CASE_VALIDATION
        )

        selected.add(
            InvestigationAnalysisStage
            .UNIFIED_CONTEXT
        )

        changed = True

        while changed:

            changed = False

            for stage in tuple(
                selected
            ):

                dependencies = (
                    INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES
                    .get(
                        stage,
                        (),
                    )
                )

                for dependency in dependencies:

                    if dependency in selected:
                        continue

                    selected.add(
                        dependency
                    )

                    changed = True

        return tuple(
            stage
            for stage
            in CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
            if stage in selected
        )

    # ======================================================
    # Integration readiness
    # ======================================================

    def connected_stages(
        self,
    ) -> tuple[
        InvestigationAnalysisStage,
        ...,
    ]:
        """
        Return currently connected executable stages.
        """

        return tuple(
            stage
            for stage
            in CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
            if stage in self._stage_handlers
        )

    def missing_handlers(
        self,
        execution_plan: tuple[
            InvestigationAnalysisStage,
            ...,
        ],
    ) -> tuple[
        InvestigationAnalysisStage,
        ...,
    ]:
        """
        Return planned stages without production handlers.
        """

        return tuple(
            stage
            for stage
            in execution_plan
            if stage
            not in self._stage_handlers
        )

    def _ensure_execution_ready(
        self,
        execution_plan: tuple[
            InvestigationAnalysisStage,
            ...,
        ],
    ) -> None:
        """
        Refuse incomplete production execution.

        Missing implementation must never masquerade as SKIPPED
        analytical work.
        """

        missing = self.missing_handlers(
            execution_plan
        )

        if not missing:
            return

        missing_names = ", ".join(
            stage.value
            for stage in missing
        )

        raise RuntimeError(
            "InvestigationAnalysisOrchestrator "
            "is not fully connected for this plan. "
            "Missing stage handlers: "
            f"{missing_names}"
        )

    # ======================================================
    # Case validation
    # ======================================================

    def _run_case_validation(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request
        del stage_result_map

        case = (
            self.case_service
            .get_case(
                case_id
            )
        )

        if case is None:

            raise ValueError(
                "The selected investigation "
                "does not exist."
            )

        return case

    # ======================================================
    # Entity Resolution
    # ======================================================

    def _run_entity_resolution_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request
        del stage_result_map

        return (
            self
            .investigation_entity_resolution_analysis_service
            .analyze_case(
                case_id
            )
        )

    # ======================================================
    # Evidence
    # ======================================================

    def _run_evidence_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request
        del stage_result_map

        return (
            self
            .investigation_evidence_analysis_service
            .analyze_case(
                case_id
            )
        )

    # ======================================================
    # Graph
    # ======================================================

    def _run_graph_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request
        del stage_result_map

        return (
            self.investigation_graph_analysis_service
            .analyze_case(
                case_id
            )
        )

    # ======================================================
    # Temporal
    # ======================================================

    def _run_temporal_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request
        del stage_result_map

        return (
            self.investigation_temporal_analysis_service
            .analyze_case(
                case_id
            )
        )

    # ======================================================
    # Anomaly
    # ======================================================

    def _run_anomaly_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request

        graph_result = (
            self._require_successful_stage_value(
                InvestigationAnalysisStage.GRAPH,
                stage_result_map,
            )
        )

        temporal_result = (
            self._require_successful_stage_value(
                InvestigationAnalysisStage.TEMPORAL,
                stage_result_map,
            )
        )

        return (
            self.investigation_anomaly_analysis_service
            .analyze_precomputed(
                case_id=case_id,
                graph_result=graph_result,
                temporal_result=temporal_result,
            )
        )

    # ======================================================
    # Clustering
    # ======================================================

    def _run_entity_clustering(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:

        del request

        graph_result = (
            self._require_successful_stage_value(
                InvestigationAnalysisStage.GRAPH,
                stage_result_map,
            )
        )

        temporal_result = (
            self._require_successful_stage_value(
                InvestigationAnalysisStage.TEMPORAL,
                stage_result_map,
            )
        )

        feature_extraction = None

        anomaly_stage_result = (
            stage_result_map.get(
                InvestigationAnalysisStage.ANOMALY
            )
        )

        if (
            anomaly_stage_result is not None
            and anomaly_stage_result.status
            == InvestigationAnalysisStageStatus.SUCCESS
            and anomaly_stage_result.result
            is not None
        ):

            feature_extraction = getattr(
                anomaly_stage_result.result,
                "features",
                None,
            )

        return (
            self.investigation_entity_clustering_service
            .analyze_precomputed(
                case_id=case_id,
                graph_result=graph_result,
                temporal_result=temporal_result,
                feature_extraction=(
                    feature_extraction
                ),
            )
        )

    # ======================================================
    # Unified analytical context
    # ======================================================

    def _run_multimodal_analysis(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> InvestigationMultimodalAnalysisResult:
        """Execute the read-only multimodal evidence bridge."""

        return (
            self.investigation_multimodal_analysis_service
            .analyze_case(case_id)
        )

    def _run_rag_retrieval(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> InvestigationRAGRetrievalResult:
        """
        Execute exactly one case-scoped RAG retrieval package.

        All retrieval/ranking remains owned by the existing
        InvestigationRAGRetrievalService -> UnifiedSearchService
        pipeline.  No search or vector logic lives here.
        """

        question = str(
            request.question
            or "What information in this investigation is most relevant to the current analysis?"
        ).strip()

        retrieval = (
            self.investigation_rag_retrieval_service
            .retrieve(
                question=question,
                case_id=case_id,
                metadata={
                    "orchestrated": True,
                    "orchestrator_version": self.VERSION,
                },
            )
        )

        # Build one bounded context for the whole Analyze run.
        # Future Summary/Conclusions handlers consume this exact
        # object instead of rebuilding retrieval/context independently.
        rag_context = (
            self.investigation_rag_context_builder
            .build(retrieval)
        )

        run_artifacts["rag_context"] = rag_context

        # Generate the investigation summary from the exact retrieval
        # and bounded context already created in this Analyze run.
        # summarize_precomputed() performs no retrieval and no context
        # construction, preserving the single-run RAG contract.
        rag_summary = (
            self.investigation_rag_summary_service
            .summarize_precomputed(
                retrieval=retrieval,
                context=rag_context,
                question=question,
            )
        )

        run_artifacts["rag_summary"] = rag_summary

        # Validate only whether model-generated [R#] references point
        # to sources that were actually included in this bounded context.
        # This is deterministic provenance validation, not truth checking.
        summary_citations = (
            self.investigation_rag_grounded_citation_service
            .validate_summary(rag_summary)
        )

        run_artifacts["summary_citations"] = summary_citations

        # Generate all approved AI conclusion workflows from the exact
        # same retrieval and bounded context created above.  The
        # precomputed entry point performs no retrieval/context rebuild.
        rag_conclusions = (
            self.investigation_rag_conclusions_service
            .analyze_precomputed(
                retrieval=retrieval,
                context=rag_context,
                question=question,
            )
        )

        run_artifacts["rag_conclusions"] = rag_conclusions

        # Validate each conclusion workflow independently against the
        # exact bounded context supplied to the model. This performs
        # deterministic reference/provenance validation only; it does
        # not regenerate conclusions and does not treat valid refs as truth.
        conclusions_citations = (
            self.investigation_rag_grounded_citation_service
            .validate_conclusions(rag_conclusions)
        )

        run_artifacts["conclusions_citations"] = conclusions_citations

        return retrieval

    def _run_unified_context(
        self,
        case_id: UUID,
        request: InvestigationAnalysisRequest,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        run_artifacts: dict[str, object],
    ) -> object:
        """
        Assemble already calculated analytical results.

        This stage performs aggregation only. It does not execute
        Graph, Temporal, Anomaly, Clustering, search or AI.
        """

        entity_resolution = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.ENTITY_RESOLUTION,
                stage_result_map,
            )
        )

        evidence = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.EVIDENCE,
                stage_result_map,
            )
        )

        graph = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.GRAPH,
                stage_result_map,
            )
        )

        temporal = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.TEMPORAL,
                stage_result_map,
            )
        )

        anomaly = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.ANOMALY,
                stage_result_map,
            )
        )

        clustering = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.CLUSTERING,
                stage_result_map,
            )
        )

        multimodal = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.MULTIMODAL,
                stage_result_map,
            )
        )

        multimodal_results = (
            ()
            if multimodal is None
            else tuple(multimodal.signals)
        )

        rag_retrieval = (
            self._optional_successful_stage_value(
                InvestigationAnalysisStage.RAG,
                stage_result_map,
            )
        )

        rag_context = run_artifacts.get(
            "rag_context"
        )

        if (
            rag_context is not None
            and not isinstance(
                rag_context,
                InvestigationRAGContext,
            )
        ):
            raise TypeError(
                "run_artifacts['rag_context'] must be "
                "InvestigationRAGContext."
            )

        rag_summary = run_artifacts.get(
            "rag_summary"
        )

        if (
            rag_summary is not None
            and not isinstance(
                rag_summary,
                InvestigationRAGSummaryResult,
            )
        ):
            raise TypeError(
                "run_artifacts['rag_summary'] must be "
                "InvestigationRAGSummaryResult."
            )

        rag_conclusions = run_artifacts.get(
            "rag_conclusions"
        )

        if (
            rag_conclusions is not None
            and not isinstance(
                rag_conclusions,
                InvestigationRAGConclusionsResult,
            )
        ):
            raise TypeError(
                "run_artifacts['rag_conclusions'] must be "
                "InvestigationRAGConclusionsResult."
            )

        summary_citations = run_artifacts.get(
            "summary_citations"
        )

        if (
            summary_citations is not None
            and not isinstance(
                summary_citations,
                InvestigationRAGCitationValidation,
            )
        ):
            raise TypeError(
                "run_artifacts['summary_citations'] must be "
                "InvestigationRAGCitationValidation."
            )

        conclusions_citations = run_artifacts.get(
            "conclusions_citations"
        )

        if (
            conclusions_citations is not None
            and not isinstance(
                conclusions_citations,
                InvestigationRAGConclusionsCitationValidation,
            )
        ):
            raise TypeError(
                "run_artifacts['conclusions_citations'] must be "
                "InvestigationRAGConclusionsCitationValidation."
            )

        warnings = (
            self._collect_context_warnings(
                stage_result_map
            )
        )

        return (
            self
            .investigation_unified_analytical_context_service
            .assemble(
                case_id=case_id,
                entity_resolution_results=(
                    ()
                    if entity_resolution is None
                    else (
                        entity_resolution,
                    )
                ),
                evidence_results=(
                    ()
                    if evidence is None
                    else (
                        evidence,
                    )
                ),
                graph=graph,
                temporal=temporal,
                anomaly=anomaly,
                clustering=clustering,
                multimodal_results=(
                    multimodal_results
                ),
                rag_retrieval=rag_retrieval,
                rag_context=rag_context,
                rag_summary=rag_summary,
                rag_conclusions=rag_conclusions,
                summary_citations=summary_citations,
                conclusions_citations=conclusions_citations,
                warnings=warnings,
                metadata={
                    "orchestrated": True,
                    "orchestrator_version": (
                        self.VERSION
                    ),
                    "question_supplied": bool(
                        request.question
                    ),
                },
            )
        )

    @staticmethod
    def _optional_successful_stage_value(
        stage: InvestigationAnalysisStage,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
    ) -> object | None:
        """
        Return a successful stage value when available.

        Missing, failed, skipped and cancelled stages contribute
        None to the partial Unified Analytical Context.
        """

        stage_result = (
            stage_result_map.get(
                stage
            )
        )

        if stage_result is None:
            return None

        if (
            stage_result.status
            != InvestigationAnalysisStageStatus.SUCCESS
        ):
            return None

        return stage_result.result

    @staticmethod
    def _collect_context_warnings(
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
    ) -> tuple[str, ...]:
        """
        Build safe warnings for the partial analytical context.

        Tracebacks are intentionally excluded.
        """

        warnings: list[str] = []

        for stage in (
            CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
        ):

            stage_result = (
                stage_result_map.get(
                    stage
                )
            )

            if stage_result is None:
                continue

            for warning in (
                stage_result.warnings
            ):

                warnings.append(
                    f"{stage.value}: {warning}"
                )

            if (
                stage_result.status
                == InvestigationAnalysisStageStatus.FAILED
                and stage_result.error
                is not None
            ):

                warnings.append(
                    (
                        f"{stage.value}: "
                        f"{stage_result.error.message}"
                    )
                )

        return tuple(
            warnings
        )

    # ======================================================
    # Shared stage-result access
    # ======================================================

    @staticmethod
    def _require_successful_stage_value(
        stage: InvestigationAnalysisStage,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
    ) -> object:
        """
        Return one successful dependency result.

        Dependency policy should normally prevent this method from
        seeing missing/failed results. The explicit guard protects
        direct handler use and future integration changes.
        """

        stage_result = (
            stage_result_map.get(
                stage
            )
        )

        if stage_result is None:

            raise RuntimeError(
                "Required analysis result "
                f"is unavailable: {stage.value}"
            )

        if (
            stage_result.status
            != InvestigationAnalysisStageStatus.SUCCESS
        ):

            raise RuntimeError(
                "Required analysis stage "
                "did not complete successfully: "
                f"{stage.value}"
            )

        if stage_result.result is None:

            raise RuntimeError(
                "Required analysis stage "
                "returned no result: "
                f"{stage.value}"
            )

        return stage_result.result

    # ======================================================
    # Dependency policy
    # ======================================================

    @staticmethod
    def _get_dependency_skip_warning(
        *,
        stage: InvestigationAnalysisStage,
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
    ) -> str | None:

        dependencies = (
            INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES
            .get(
                stage,
                (),
            )
        )

        for dependency in dependencies:

            dependency_result = (
                stage_result_map.get(
                    dependency
                )
            )

            if dependency_result is None:

                return (
                    "Skipped because required "
                    f"{dependency.value} analysis "
                    "is unavailable."
                )

            if (
                dependency_result.status
                != InvestigationAnalysisStageStatus.SUCCESS
            ):

                return (
                    "Skipped because required "
                    f"{dependency.value} analysis "
                    "did not complete successfully."
                )

        return None

    # ======================================================
    # Cancellation
    # ======================================================

    @staticmethod
    def _is_cancelled(
        cancellation_token: (
            InvestigationAnalysisCancellationToken
            | None
        ),
    ) -> bool:

        if cancellation_token is None:

            return False

        try:

            return bool(
                cancellation_token
                .is_cancelled()
            )

        except Exception:

            logger.exception(
                "Investigation analysis "
                "cancellation token failed."
            )

            return False

    def _append_cancelled_stages(
        self,
        *,
        case_id: UUID,
        execution_plan: tuple[
            InvestigationAnalysisStage,
            ...,
        ],
        starting_index: int,
        stage_results: list[
            InvestigationAnalysisStageResult
        ],
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ),
    ) -> None:

        for zero_based_index in range(
            starting_index,
            len(
                execution_plan
            ),
        ):

            stage = execution_plan[
                zero_based_index
            ]

            if stage in stage_result_map:
                continue

            stage_result = (
                InvestigationAnalysisStageResult(
                    stage=stage,
                    status=(
                        InvestigationAnalysisStageStatus
                        .CANCELLED
                    ),
                )
            )

            stage_results.append(
                stage_result
            )

            stage_result_map[
                stage
            ] = stage_result

            self._emit_stage_finished(
                case_id=case_id,
                stage=stage,
                stage_result=stage_result,
                stage_index=(
                    zero_based_index
                    + 1
                ),
                stage_count=len(
                    execution_plan
                ),
                progress_callback=(
                    progress_callback
                ),
            )

    def _append_skipped_stages(
        self,
        *,
        case_id: UUID,
        execution_plan: tuple[
            InvestigationAnalysisStage,
            ...,
        ],
        starting_index: int,
        reason: str,
        stage_results: list[
            InvestigationAnalysisStageResult
        ],
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ),
    ) -> None:

        for zero_based_index in range(
            starting_index,
            len(
                execution_plan
            ),
        ):

            stage = execution_plan[
                zero_based_index
            ]

            if stage in stage_result_map:
                continue

            stage_result = (
                InvestigationAnalysisStageResult(
                    stage=stage,
                    status=(
                        InvestigationAnalysisStageStatus
                        .SKIPPED
                    ),
                    warnings=(
                        reason,
                    ),
                )
            )

            stage_results.append(
                stage_result
            )

            stage_result_map[
                stage
            ] = stage_result

            self._emit_stage_finished(
                case_id=case_id,
                stage=stage,
                stage_result=stage_result,
                stage_index=(
                    zero_based_index
                    + 1
                ),
                stage_count=len(
                    execution_plan
                ),
                progress_callback=(
                    progress_callback
                ),
            )

    # ======================================================
    # Progress
    # ======================================================

    @staticmethod
    def _emit_progress(
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ),
        event: InvestigationAnalysisProgressEvent,
    ) -> None:

        if progress_callback is None:

            return

        try:

            progress_callback(
                event
            )

        except Exception:

            logger.exception(
                "Investigation analysis "
                "progress callback failed."
            )

    def _emit_stage_finished(
        self,
        *,
        case_id: UUID,
        stage: InvestigationAnalysisStage,
        stage_result: (
            InvestigationAnalysisStageResult
        ),
        stage_index: int,
        stage_count: int,
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ),
    ) -> None:

        self._emit_progress(
            progress_callback,
            InvestigationAnalysisProgressEvent(
                case_id=case_id,
                event_type=(
                    InvestigationAnalysisProgressEventType
                    .STAGE_FINISHED
                ),
                stage=stage,
                stage_status=(
                    stage_result.status
                ),
                stage_index=stage_index,
                stage_count=stage_count,
                message=(
                    self._stage_finished_message(
                        stage,
                        stage_result.status,
                    )
                ),
            ),
        )

    # ======================================================
    # Result policy
    # ======================================================

    @staticmethod
    def _determine_status(
        *,
        stage_results: tuple[
            InvestigationAnalysisStageResult,
            ...,
        ],
        cancelled: bool,
    ) -> InvestigationAnalysisStatus:

        if cancelled:

            return (
                InvestigationAnalysisStatus
                .CANCELLED
            )

        validation_result = next(
            (
                result
                for result
                in stage_results
                if (
                    result.stage
                    == InvestigationAnalysisStage
                    .CASE_VALIDATION
                )
            ),
            None,
        )

        if (
            validation_result is None
            or validation_result.status
            != InvestigationAnalysisStageStatus.SUCCESS
        ):

            return (
                InvestigationAnalysisStatus
                .FAILED
            )

        failed_results = tuple(
            result
            for result
            in stage_results
            if (
                result.status
                == InvestigationAnalysisStageStatus.FAILED
            )
        )

        if not failed_results:

            return (
                InvestigationAnalysisStatus
                .SUCCESS
            )

        successful_analytical_results = tuple(
            result
            for result
            in stage_results
            if (
                result.status
                == InvestigationAnalysisStageStatus.SUCCESS
                and result.stage
                != InvestigationAnalysisStage.CASE_VALIDATION
            )
        )

        if successful_analytical_results:

            return (
                InvestigationAnalysisStatus
                .PARTIAL
            )

        return (
            InvestigationAnalysisStatus
            .FAILED
        )

    @staticmethod
    def _extract_unified_context(
        stage_result_map: dict[
            InvestigationAnalysisStage,
            InvestigationAnalysisStageResult,
        ],
    ) -> Any | None:

        stage_result = (
            stage_result_map.get(
                InvestigationAnalysisStage
                .UNIFIED_CONTEXT
            )
        )

        if stage_result is None:

            return None

        if (
            stage_result.status
            != InvestigationAnalysisStageStatus.SUCCESS
        ):

            return None

        return stage_result.result

    # ======================================================
    # Human-readable progress messages
    # ======================================================

    @staticmethod
    def _stage_started_message(
        stage: InvestigationAnalysisStage,
    ) -> str:

        messages = {
            InvestigationAnalysisStage.CASE_VALIDATION: (
                "Validating investigation."
            ),
            InvestigationAnalysisStage.ENTITY_RESOLUTION: (
                "Analyzing entity resolution."
            ),
            InvestigationAnalysisStage.EVIDENCE: (
                "Analyzing evidence."
            ),
            InvestigationAnalysisStage.GRAPH: (
                "Analyzing investigation graph."
            ),
            InvestigationAnalysisStage.TEMPORAL: (
                "Analyzing temporal patterns."
            ),
            InvestigationAnalysisStage.ANOMALY: (
                "Detecting anomalies."
            ),
            InvestigationAnalysisStage.CLUSTERING: (
                "Clustering investigation entities."
            ),
            InvestigationAnalysisStage.MULTIMODAL: (
                "Analyzing multimodal evidence."
            ),
            InvestigationAnalysisStage.RAG: (
                "Generating grounded AI analysis."
            ),
            InvestigationAnalysisStage.UNIFIED_CONTEXT: (
                "Assembling analytical context."
            ),
        }

        return messages[
            stage
        ]

    @staticmethod
    def _stage_finished_message(
        stage: InvestigationAnalysisStage,
        status: InvestigationAnalysisStageStatus,
    ) -> str:

        stage_name = (
            stage.value.replace(
                "_",
                " ",
            )
        )

        if (
            status
            == InvestigationAnalysisStageStatus.SUCCESS
        ):

            return (
                f"{stage_name.capitalize()} completed."
            )

        if (
            status
            == InvestigationAnalysisStageStatus.SKIPPED
        ):

            return (
                f"{stage_name.capitalize()} skipped."
            )

        if (
            status
            == InvestigationAnalysisStageStatus.CANCELLED
        ):

            return (
                f"{stage_name.capitalize()} cancelled."
            )

        return (
            f"{stage_name.capitalize()} failed."
        )

    @staticmethod
    def _analysis_finished_message(
        status: InvestigationAnalysisStatus,
    ) -> str:

        if (
            status
            == InvestigationAnalysisStatus.SUCCESS
        ):

            return (
                "Investigation analysis completed."
            )

        if (
            status
            == InvestigationAnalysisStatus.PARTIAL
        ):

            return (
                "Investigation analysis completed "
                "with partial results."
            )

        if (
            status
            == InvestigationAnalysisStatus.CANCELLED
        ):

            return (
                "Investigation analysis was cancelled."
            )

        return (
            "Investigation analysis failed."
        )


__all__ = [
    "InvestigationAnalysisOrchestrator",
]
