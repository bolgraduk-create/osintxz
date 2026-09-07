"""
Investigation RAG summary service.

Creates an AI-generated investigation summary through the
new Unified Search based RAG pipeline.

Architecture:

case_id
    ↓
InvestigationRAGRetrievalService
    ↓
UnifiedSearchService
    ↓
InvestigationRAGContextBuilder
    ↓
InvestigationRAGPromptService
    ↓
AIExecutionService.generate_text()
    ↓
InvestigationRAGSummaryResult

This service is intentionally separate from
InvestigationSummaryBuilder.

InvestigationSummaryBuilder:
    deterministic Markdown/report summary.

InvestigationRAGSummaryService:
    AI-generated bounded RAG summary.

Responsibilities:

- orchestrate existing RAG components
- retrieve investigation sources
- build bounded context
- build a RAG prompt
- execute the rendered prompt through the existing
  AI execution layer
- return source references and generation metadata

Does NOT:

- replace InvestigationSummaryBuilder
- create reports
- write AIAnalysis records
- commit database transactions
- create another search engine
- create another PromptManager
- create another AI provider
- validate final grounded citations
- treat model output as verified fact
- modify evidence confidence
- perform Entity Resolution

Important boundaries:

AI summary != verified investigation fact
retrieval score != evidence confidence
R1 / R2 / R3 != validated citation
summary generation != AI conclusions layer

Grounded citation validation and AI conclusions are separate
later Block 9 stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol
from uuid import UUID

from app.services.investigation_rag_context_builder import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_MAX_SOURCE_CHARS,
    InvestigationRAGContext,
    InvestigationRAGContextBuilder,
)

from app.services.investigation_rag_prompt_service import (
    InvestigationRAGPrompt,
    InvestigationRAGPromptService,
)

from app.services.investigation_rag_retrieval_service import (
    DEFAULT_RAG_CANDIDATE_LIMIT,
    DEFAULT_RAG_RESULT_LIMIT,
    InvestigationRAGRetrievalResult,
    InvestigationRAGRetrievalService,
)


# ==========================================================
# Defaults
# ==========================================================

DEFAULT_INVESTIGATION_SUMMARY_QUESTION = (
    "Summarize the most relevant information in this "
    "investigation. Identify important facts, entities, "
    "relationships, chronology, contradictions, uncertainties "
    "and significant missing information."
)


# ==========================================================
# AI execution protocol
# ==========================================================


class InvestigationRAGTextExecutor(
    Protocol
):
    """
    Minimal AI execution contract needed by this service.

    The production implementation is the existing
    AIExecutionService.generate_text().
    """

    def generate_text(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        ...


# ==========================================================
# Result contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGSummaryResult:
    """
    One AI-generated investigation summary.

    `summary` is model output and must not automatically be
    treated as verified evidence or a factual conclusion.
    """

    case_id: UUID

    question: str

    status: str

    summary: str

    source_references: tuple[
        str,
        ...,
    ]

    retrieval: InvestigationRAGRetrievalResult

    context: InvestigationRAGContext

    prompt: InvestigationRAGPrompt | None

    model_info: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    warnings: tuple[
        str,
        ...,
    ] = ()

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def successful(
        self,
    ) -> bool:
        """
        Whether AI summary generation completed.
        """

        return (
            self.status
            ==
            "ok"
        )

    @property
    def has_summary(
        self,
    ) -> bool:
        """
        Whether model output is present.
        """

        return bool(
            self.summary.strip()
        )

    @property
    def has_sources(
        self,
    ) -> bool:
        """
        Whether summary generation had source context.
        """

        return bool(
            self.source_references
        )


# ==========================================================
# Service
# ==========================================================


class InvestigationRAGSummaryService:
    """
    Orchestrates the new RAG pipeline for investigation
    summary generation.
    """

    def __init__(
        self,
        *,
        retrieval_service: InvestigationRAGRetrievalService,
        context_builder: InvestigationRAGContextBuilder,
        prompt_service: InvestigationRAGPromptService,
        ai_execution_service: InvestigationRAGTextExecutor,
    ) -> None:

        if not isinstance(
            retrieval_service,
            InvestigationRAGRetrievalService,
        ):

            raise TypeError(
                "retrieval_service must be "
                "InvestigationRAGRetrievalService."
            )

        if not isinstance(
            context_builder,
            InvestigationRAGContextBuilder,
        ):

            raise TypeError(
                "context_builder must be "
                "InvestigationRAGContextBuilder."
            )

        if not isinstance(
            prompt_service,
            InvestigationRAGPromptService,
        ):

            raise TypeError(
                "prompt_service must be "
                "InvestigationRAGPromptService."
            )

        if not callable(
            getattr(
                ai_execution_service,
                "generate_text",
                None,
            )
        ):

            raise TypeError(
                "ai_execution_service must expose "
                "generate_text(prompt, **kwargs)."
            )

        self.retrieval_service = (
            retrieval_service
        )

        self.context_builder = (
            context_builder
        )

        self.prompt_service = (
            prompt_service
        )

        self.ai_execution_service = (
            ai_execution_service
        )

    # ======================================================
    # Public API
    # ======================================================

    def summarize(
        self,
        *,
        case_id: UUID,
        question: str = (
            DEFAULT_INVESTIGATION_SUMMARY_QUESTION
        ),
        result_limit: int = (
            DEFAULT_RAG_RESULT_LIMIT
        ),
        candidate_limit: int = (
            DEFAULT_RAG_CANDIDATE_LIMIT
        ),
        max_context_chars: int = (
            DEFAULT_MAX_CONTEXT_CHARS
        ),
        max_source_chars: int = (
            DEFAULT_MAX_SOURCE_CHARS
        ),
        enable_query_expansion: bool = True,
        enable_reranking: bool = True,
        enable_neural_reranking: bool = True,
        generation_kwargs: dict[
            str,
            Any,
        ] | None = None,
    ) -> InvestigationRAGSummaryResult:
        """
        Generate one investigation RAG summary.

        If retrieval returns no usable context, the model is
        deliberately NOT called.
        """

        if not isinstance(
            case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        normalized_question = (
            self._normalize_question(
                question
            )
        )

        # --------------------------------------------------
        # Retrieval
        # --------------------------------------------------

        retrieval = (
            self.retrieval_service.retrieve(
                question=(
                    normalized_question
                ),

                case_id=case_id,

                limit=result_limit,

                candidate_limit=(
                    candidate_limit
                ),

                enable_query_expansion=(
                    enable_query_expansion
                ),

                enable_reranking=(
                    enable_reranking
                ),

                enable_neural_reranking=(
                    enable_neural_reranking
                ),
            )
        )

        # --------------------------------------------------
        # Context
        # --------------------------------------------------

        context = (
            self.context_builder.build(
                retrieval,

                max_context_chars=(
                    max_context_chars
                ),

                max_source_chars=(
                    max_source_chars
                ),
            )
        )

        warnings = list(
            retrieval.warnings
        )

        warnings.extend(
            context.warnings
        )

        # --------------------------------------------------
        # Insufficient context
        #
        # Do not ask the model to invent a case summary from
        # an empty investigation context.
        # --------------------------------------------------

        if not context.has_context:

            warnings.append(
                "Investigation summary was not generated "
                "because no usable RAG context was available."
            )

            return InvestigationRAGSummaryResult(
                case_id=case_id,

                question=(
                    normalized_question
                ),

                status=(
                    "insufficient_context"
                ),

                summary="",

                source_references=(),

                retrieval=retrieval,

                context=context,

                prompt=None,

                model_info={},

                warnings=tuple(
                    warnings
                ),

                metadata={
                    "workflow": (
                        "rag_investigation_summary"
                    ),
                    "ai_executed": False,
                },
            )

        # --------------------------------------------------
        # Prompt
        # --------------------------------------------------

        prompt = (
            self.prompt_service.build(
                context
            )
        )

        # --------------------------------------------------
        # Existing AI execution layer
        # --------------------------------------------------

        kwargs = dict(
            generation_kwargs
            or {}
        )

        response = (
            self.ai_execution_service
            .generate_text(
                prompt.text,
                **kwargs,
            )
        )

        normalized_summary = str(
            response
            or ""
        ).strip()

        if not normalized_summary:

            raise ValueError(
                "AI execution returned an empty "
                "investigation summary."
            )

        # --------------------------------------------------
        # Provider metadata
        # --------------------------------------------------

        model_info = (
            self._extract_model_info()
        )

        return InvestigationRAGSummaryResult(
            case_id=case_id,

            question=(
                normalized_question
            ),

            status="ok",

            summary=(
                normalized_summary
            ),

            source_references=(
                prompt.source_references
            ),

            retrieval=retrieval,

            context=context,

            prompt=prompt,

            model_info=(
                model_info
            ),

            warnings=tuple(
                warnings
            ),

            metadata={
                "workflow": (
                    "rag_investigation_summary"
                ),

                "ai_executed": True,

                "retrieval_source_count": (
                    retrieval.source_count
                ),

                "context_source_count": (
                    context.included_source_count
                ),

                "prompt_characters": (
                    prompt.prompt_characters
                ),

                "context_characters": (
                    context.used_chars
                ),

                "source_reference_count": len(
                    prompt.source_references
                ),
            },
        )

    def summarize_precomputed(
        self,
        *,
        retrieval: InvestigationRAGRetrievalResult,
        context: InvestigationRAGContext,
        question: str | None = None,
        generation_kwargs: dict[
            str,
            Any,
        ] | None = None,
    ) -> InvestigationRAGSummaryResult:
        """
        Generate a summary from already prepared RAG inputs.

        This entry point is intended for the unified investigation
        orchestrator. It never performs retrieval and never rebuilds
        bounded context. The exact production retrieval/context objects
        supplied by the caller are preserved in the result.
        """

        if not isinstance(
            retrieval,
            InvestigationRAGRetrievalResult,
        ):
            raise TypeError(
                "retrieval must be "
                "InvestigationRAGRetrievalResult."
            )

        if not isinstance(
            context,
            InvestigationRAGContext,
        ):
            raise TypeError(
                "context must be InvestigationRAGContext."
            )

        case_id = retrieval.case_id

        if context.case_id != case_id:
            raise ValueError(
                "retrieval and context case_id values must match."
            )

        normalized_question = (
            self._normalize_question(
                retrieval.question
                if question is None
                else question
            )
        )

        warnings = list(retrieval.warnings)
        warnings.extend(context.warnings)

        if not context.has_context:
            warnings.append(
                "Investigation summary was not generated "
                "because no usable RAG context was available."
            )

            return InvestigationRAGSummaryResult(
                case_id=case_id,
                question=normalized_question,
                status="insufficient_context",
                summary="",
                source_references=(),
                retrieval=retrieval,
                context=context,
                prompt=None,
                model_info={},
                warnings=tuple(warnings),
                metadata={
                    "workflow": "rag_investigation_summary",
                    "ai_executed": False,
                    "precomputed_inputs": True,
                },
            )

        prompt = self.prompt_service.build(context)

        kwargs = dict(generation_kwargs or {})

        response = self.ai_execution_service.generate_text(
            prompt.text,
            **kwargs,
        )

        normalized_summary = str(response or "").strip()

        if not normalized_summary:
            raise ValueError(
                "AI execution returned an empty investigation summary."
            )

        model_info = self._extract_model_info()

        return InvestigationRAGSummaryResult(
            case_id=case_id,
            question=normalized_question,
            status="ok",
            summary=normalized_summary,
            source_references=prompt.source_references,
            retrieval=retrieval,
            context=context,
            prompt=prompt,
            model_info=model_info,
            warnings=tuple(warnings),
            metadata={
                "workflow": "rag_investigation_summary",
                "ai_executed": True,
                "precomputed_inputs": True,
                "retrieval_source_count": retrieval.source_count,
                "context_source_count": context.included_source_count,
                "prompt_characters": prompt.prompt_characters,
                "context_characters": context.used_chars,
                "source_reference_count": len(
                    prompt.source_references
                ),
            },
        )

    # ======================================================
    # Metadata
    # ======================================================

    def _extract_model_info(
        self,
    ) -> dict[
        str,
        Any,
    ]:
        """
        Read model information from the existing execution
        service when available.

        Absence of metadata must not invalidate a successful
        model response.
        """

        ai_manager = getattr(
            self.ai_execution_service,
            "ai_manager",
            None,
        )

        if ai_manager is None:

            return {}

        info_method = getattr(
            ai_manager,
            "info",
            None,
        )

        if not callable(
            info_method
        ):

            return {}

        try:

            result = info_method()

        except Exception:

            return {}

        if not isinstance(
            result,
            dict,
        ):

            return {}

        return dict(
            result
        )

    # ======================================================
    # Validation
    # ======================================================

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        """
        Validate and normalize summary retrieval question.
        """

        if not isinstance(
            question,
            str,
        ):

            raise TypeError(
                "question must be a string."
            )

        normalized = (
            question.strip()
        )

        if not normalized:

            raise ValueError(
                "question cannot be empty."
            )

        return normalized
