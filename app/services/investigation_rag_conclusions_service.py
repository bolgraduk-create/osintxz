"""
Investigation RAG conclusions service.

Produces bounded AI analytical conclusions from investigation
sources retrieved through the Unified Search based RAG pipeline.

Architecture:

case_id
    ↓
InvestigationRAGRetrievalService
    ↓
UnifiedSearchService
    ↓
InvestigationRAGContextBuilder
    ↓
shared PromptManager
    ├── hypothesis_generation
    ├── contradiction_analysis
    └── next_investigation_steps
    ↓
existing AIExecutionService.generate_text()
    ↓
InvestigationRAGConclusionsResult

This layer deliberately reuses the existing investigation
workflows registered in the central PromptManager.

Responsibilities:

- retrieve investigation context once
- build one bounded RAG context
- execute selected existing analytical workflows
- preserve R1 / R2 / ... source provenance
- keep hypotheses, contradictions and next steps separate
- expose generation metadata and warnings

Does NOT:

- create another search engine
- create another context builder
- create another PromptManager
- create another AI provider
- create Evidence
- modify Evidence confidence
- perform Entity Resolution
- create Relationships
- validate grounded citations
- persist AIAnalysis records
- treat model output as verified fact
- automatically execute investigation recommendations

Important boundaries:

AI conclusion != verified fact
AI conclusion != Evidence
AI conclusion != Entity Resolution signal
AI conclusion != Relationship
retrieval score != evidence confidence
source reference != validated grounded citation

Grounded citation validation is implemented in the next
Block 9 stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Protocol
from uuid import UUID

from app.ai.prompts.prompt_manager import (
    PromptManager,
)

from app.services.investigation_rag_context_builder import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_MAX_SOURCE_CHARS,
    InvestigationRAGContext,
    InvestigationRAGContextBuilder,
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

DEFAULT_CONCLUSIONS_RETRIEVAL_QUESTION = (
    "Identify the investigation material most relevant to "
    "testable hypotheses, contradictions, inconsistencies, "
    "uncertainties and lawful next investigation steps."
)


# ==========================================================
# Conclusion kinds
# ==========================================================


class InvestigationRAGConclusionKind(
    str,
    Enum,
):
    """
    Supported analytical conclusion categories.
    """

    HYPOTHESES = (
        "hypotheses"
    )

    CONTRADICTIONS = (
        "contradictions"
    )

    NEXT_STEPS = (
        "next_steps"
    )


DEFAULT_CONCLUSION_KINDS = (
    InvestigationRAGConclusionKind.HYPOTHESES,
    InvestigationRAGConclusionKind.CONTRADICTIONS,
    InvestigationRAGConclusionKind.NEXT_STEPS,
)


WORKFLOW_BY_KIND = {
    InvestigationRAGConclusionKind.HYPOTHESES: (
        "hypothesis_generation"
    ),

    InvestigationRAGConclusionKind.CONTRADICTIONS: (
        "contradiction_analysis"
    ),

    InvestigationRAGConclusionKind.NEXT_STEPS: (
        "next_investigation_steps"
    ),
}


# ==========================================================
# AI execution protocol
# ==========================================================


class InvestigationRAGConclusionExecutor(
    Protocol
):
    """
    Minimal AI execution contract required here.

    Production implementation:
        AIExecutionService.generate_text()
    """

    def generate_text(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        ...


# ==========================================================
# Individual conclusion
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGConclusion:
    """
    Result of one analytical workflow.

    `text` is AI-generated analytical material and is not
    automatically considered a verified investigation fact.
    """

    kind: InvestigationRAGConclusionKind

    workflow_name: str

    text: str

    source_references: tuple[
        str,
        ...,
    ]

    prompt_characters: int

    response_characters: int

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def has_text(
        self,
    ) -> bool:
        """
        Whether this workflow produced output.
        """

        return bool(
            self.text.strip()
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGConclusionsResult:
    """
    Complete RAG conclusions result for one case.
    """

    case_id: UUID

    question: str

    status: str

    conclusions: tuple[
        InvestigationRAGConclusion,
        ...,
    ]

    source_references: tuple[
        str,
        ...,
    ]

    retrieval: InvestigationRAGRetrievalResult

    context: InvestigationRAGContext

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
        Whether requested analytical workflows completed.
        """

        return (
            self.status
            ==
            "ok"
        )

    @property
    def has_context(
        self,
    ) -> bool:
        """
        Whether usable investigation context existed.
        """

        return (
            self.context.has_context
        )

    @property
    def has_conclusions(
        self,
    ) -> bool:
        """
        Whether at least one workflow produced output.
        """

        return bool(
            self.conclusions
        )

    @property
    def conclusion_count(
        self,
    ) -> int:
        """
        Number of completed conclusion workflows.
        """

        return len(
            self.conclusions
        )

    def get(
        self,
        kind: InvestigationRAGConclusionKind,
    ) -> InvestigationRAGConclusion | None:
        """
        Return conclusion by category.
        """

        for conclusion in (
            self.conclusions
        ):

            if (
                conclusion.kind
                ==
                kind
            ):

                return conclusion

        return None


# ==========================================================
# Service
# ==========================================================


class InvestigationRAGConclusionsService:
    """
    Generates analytical conclusions over bounded RAG context.
    """

    def __init__(
        self,
        *,
        retrieval_service: InvestigationRAGRetrievalService,
        context_builder: InvestigationRAGContextBuilder,
        prompt_manager: PromptManager,
        ai_execution_service: InvestigationRAGConclusionExecutor,
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
            prompt_manager,
            PromptManager,
        ):

            raise TypeError(
                "prompt_manager must be PromptManager."
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

        self.prompt_manager = (
            prompt_manager
        )

        self.ai_execution_service = (
            ai_execution_service
        )

        self._validate_workflows()

    # ======================================================
    # Public API
    # ======================================================

    def analyze(
        self,
        *,
        case_id: UUID,
        question: str = (
            DEFAULT_CONCLUSIONS_RETRIEVAL_QUESTION
        ),
        kinds: tuple[
            InvestigationRAGConclusionKind,
            ...,
        ] | None = None,
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
    ) -> InvestigationRAGConclusionsResult:
        """
        Generate selected analytical conclusions.

        Retrieval and context construction happen exactly once.

        The model is never called when no usable investigation
        context exists.
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

        selected_kinds = (
            self._normalize_kinds(
                kinds
            )
        )

        # --------------------------------------------------
        # Retrieve once
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
        # Build context once
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

        source_references = tuple(
            source.reference_id
            for source in (
                context.included_sources
            )
        )

        # --------------------------------------------------
        # No-context guard
        # --------------------------------------------------

        if not context.has_context:

            warnings.append(
                "AI conclusions were not generated because "
                "no usable RAG context was available."
            )

            return (
                InvestigationRAGConclusionsResult(
                    case_id=case_id,

                    question=(
                        normalized_question
                    ),

                    status=(
                        "insufficient_context"
                    ),

                    conclusions=(),

                    source_references=(),

                    retrieval=retrieval,

                    context=context,

                    model_info={},

                    warnings=tuple(
                        warnings
                    ),

                    metadata={
                        "workflow": (
                            "rag_ai_conclusions"
                        ),

                        "ai_executed": False,

                        "requested_conclusion_count": (
                            len(
                                selected_kinds
                            )
                        ),

                        "completed_conclusion_count": 0,
                    },
                )
            )

        # --------------------------------------------------
        # Grounded workflow context
        # --------------------------------------------------

        workflow_context = (
            self._build_workflow_context(
                context
            )
        )

        kwargs = dict(
            generation_kwargs
            or {}
        )

        generated: list[
            InvestigationRAGConclusion
        ] = []

        # --------------------------------------------------
        # Existing PromptManager workflows
        # --------------------------------------------------

        for kind in selected_kinds:

            workflow_name = (
                WORKFLOW_BY_KIND[
                    kind
                ]
            )

            prompt = (
                self.prompt_manager
                .render_prompt(
                    workflow_name,
                    {
                        "context": (
                            workflow_context
                        ),
                    },
                )
            )

            normalized_prompt = str(
                prompt
                or ""
            ).strip()

            if not normalized_prompt:

                raise ValueError(
                    "PromptManager returned an empty "
                    f"prompt for {workflow_name}."
                )

            response = (
                self.ai_execution_service
                .generate_text(
                    normalized_prompt,
                    **kwargs,
                )
            )

            normalized_response = str(
                response
                or ""
            ).strip()

            if not normalized_response:

                raise ValueError(
                    "AI execution returned an empty "
                    f"response for {workflow_name}."
                )

            generated.append(
                InvestigationRAGConclusion(
                    kind=kind,

                    workflow_name=(
                        workflow_name
                    ),

                    text=(
                        normalized_response
                    ),

                    source_references=(
                        source_references
                    ),

                    prompt_characters=len(
                        normalized_prompt
                    ),

                    response_characters=len(
                        normalized_response
                    ),

                    metadata={
                        "model_output": True,

                        "verified_fact": False,

                        "grounded_citation_validated": False,
                    },
                )
            )

        model_info = (
            self._extract_model_info()
        )

        return InvestigationRAGConclusionsResult(
            case_id=case_id,

            question=(
                normalized_question
            ),

            status="ok",

            conclusions=tuple(
                generated
            ),

            source_references=(
                source_references
            ),

            retrieval=retrieval,

            context=context,

            model_info=(
                model_info
            ),

            warnings=tuple(
                warnings
            ),

            metadata={
                "workflow": (
                    "rag_ai_conclusions"
                ),

                "ai_executed": True,

                "retrieval_source_count": (
                    retrieval.source_count
                ),

                "context_source_count": (
                    context.included_source_count
                ),

                "requested_conclusion_count": (
                    len(
                        selected_kinds
                    )
                ),

                "completed_conclusion_count": (
                    len(
                        generated
                    )
                ),

                "source_reference_count": (
                    len(
                        source_references
                    )
                ),

                "persistent": False,

                "grounded_citation_validation": False,
            },
        )

    def analyze_precomputed(
        self,
        *,
        retrieval: InvestigationRAGRetrievalResult,
        context: InvestigationRAGContext,
        question: str | None = None,
        kinds: tuple[
            InvestigationRAGConclusionKind,
            ...,
        ] | None = None,
        generation_kwargs: dict[
            str,
            Any,
        ] | None = None,
    ) -> InvestigationRAGConclusionsResult:
        """
        Generate conclusions from already prepared RAG inputs.

        This entry point is intended for the unified investigation
        orchestrator. It never performs retrieval and never rebuilds
        bounded context. The supplied production retrieval/context
        objects are preserved in the returned result.
        """

        if not isinstance(
            retrieval,
            InvestigationRAGRetrievalResult,
        ):
            raise TypeError(
                "retrieval must be InvestigationRAGRetrievalResult."
            )

        if not isinstance(
            context,
            InvestigationRAGContext,
        ):
            raise TypeError(
                "context must be InvestigationRAGContext."
            )

        if context.case_id != retrieval.case_id:
            raise ValueError(
                "retrieval and context must belong to the same case."
            )

        normalized_question = self._normalize_question(
            question or retrieval.question
        )

        if context.case_id != retrieval.case_id:
            raise ValueError(
                "context case_id does not match retrieval case_id."
            )

        selected_kinds = self._normalize_kinds(kinds)

        warnings = list(retrieval.warnings)
        warnings.extend(context.warnings)

        source_references = tuple(
            source.reference_id
            for source in context.included_sources
        )

        if not context.has_context:
            warnings.append(
                "AI conclusions were not generated because "
                "no usable RAG context was available."
            )

            return InvestigationRAGConclusionsResult(
                case_id=retrieval.case_id,
                question=normalized_question,
                status="insufficient_context",
                conclusions=(),
                source_references=(),
                retrieval=retrieval,
                context=context,
                model_info={},
                warnings=tuple(warnings),
                metadata={
                    "workflow": "rag_ai_conclusions",
                    "ai_executed": False,
                    "precomputed_inputs": True,
                    "requested_conclusion_count": len(selected_kinds),
                    "completed_conclusion_count": 0,
                },
            )

        workflow_context = self._build_workflow_context(
            context,
            question=normalized_question,
        )
        kwargs = dict(generation_kwargs or {})

        generated: list[InvestigationRAGConclusion] = []

        for kind in selected_kinds:
            workflow_name = WORKFLOW_BY_KIND[kind]

            prompt = self.prompt_manager.render_prompt(
                workflow_name,
                {
                    "context": workflow_context,
                },
            )

            normalized_prompt = str(prompt or "").strip()
            if not normalized_prompt:
                raise ValueError(
                    "PromptManager returned an empty prompt for "
                    f"{workflow_name}."
                )

            response = self.ai_execution_service.generate_text(
                normalized_prompt,
                **kwargs,
            )

            normalized_response = str(response or "").strip()
            if not normalized_response:
                raise ValueError(
                    "AI execution returned an empty response for "
                    f"{workflow_name}."
                )

            generated.append(
                InvestigationRAGConclusion(
                    kind=kind,
                    workflow_name=workflow_name,
                    text=normalized_response,
                    source_references=source_references,
                    prompt_characters=len(normalized_prompt),
                    response_characters=len(normalized_response),
                    metadata={
                        "model_output": True,
                        "verified_fact": False,
                        "grounded_citation_validated": False,
                    },
                )
            )

        model_info = self._extract_model_info()

        return InvestigationRAGConclusionsResult(
            case_id=retrieval.case_id,
            question=normalized_question,
            status="ok",
            conclusions=tuple(generated),
            source_references=source_references,
            retrieval=retrieval,
            context=context,
            model_info=model_info,
            warnings=tuple(warnings),
            metadata={
                "workflow": "rag_ai_conclusions",
                "ai_executed": True,
                "precomputed_inputs": True,
                "retrieval_source_count": retrieval.source_count,
                "context_source_count": context.included_source_count,
                "requested_conclusion_count": len(selected_kinds),
                "completed_conclusion_count": len(generated),
                "source_reference_count": len(source_references),
                "persistent": False,
                "grounded_citation_validation": False,
            },
        )

    # ======================================================
    # Workflow validation
    # ======================================================

    def _validate_workflows(
        self,
    ) -> None:
        """
        Ensure existing central prompts remain compatible.

        All currently selected conclusion workflows must accept
        exactly one required variable: context.
        """

        for workflow_name in (
            WORKFLOW_BY_KIND.values()
        ):

            if not self.prompt_manager.has_prompt(
                workflow_name
            ):

                raise RuntimeError(
                    "Required investigation prompt "
                    f"'{workflow_name}' is not registered."
                )

            required = set(
                self.prompt_manager
                .get_required_variables(
                    workflow_name
                )
            )

            if required != {
                "context",
            }:

                raise RuntimeError(
                    "Investigation prompt "
                    f"'{workflow_name}' has incompatible "
                    "required variables."
                )

    # ======================================================
    # Grounding instructions
    # ======================================================

    @staticmethod
    def _build_workflow_context(
        context: InvestigationRAGContext,
        *,
        question: str = "",
    ) -> str:
        """
        Prepare bounded RAG material for legacy analytical
        workflow prompts.

        The original context and R1 / R2 / ... order are
        preserved exactly after the instruction header.
        """

        return (
            "ANALYST QUESTION / FOCUS:\n"
            f"{str(question or '').strip()}\n\n"
            "GROUNDING RULES:\n"
            "- Use only the investigation sources supplied below.\n"
            "- Source-specific statements should identify the "
            "relevant source reference such as [R1] or [R2].\n"
            "- A retrieved source is source material, not "
            "automatically a verified fact.\n"
            "- retrieval_score represents search relevance, not "
            "evidence confidence.\n"
            "- Clearly separate direct observations from "
            "analytical inference.\n"
            "- Hypotheses must remain hypotheses.\n"
            "- Contradictions must not automatically be interpreted "
            "as deception.\n"
            "- Do not infer that similar identities represent the "
            "same entity without sufficient support.\n"
            "- Recommendations must be lawful and proportionate.\n"
            "- Source references are provenance markers only; "
            "grounded citation validation occurs separately.\n\n"

            "RETRIEVED INVESTIGATION SOURCES:\n"
            f"{context.text}"
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
        Read provider information without making it required
        for a successful analytical response.
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
        Normalize retrieval question.
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

    @staticmethod
    def _normalize_kinds(
        kinds: tuple[
            InvestigationRAGConclusionKind,
            ...,
        ] | None,
    ) -> tuple[
        InvestigationRAGConclusionKind,
        ...,
    ]:
        """
        Validate conclusion categories and remove duplicates
        while preserving requested order.
        """

        values = (
            DEFAULT_CONCLUSION_KINDS
            if kinds is None
            else kinds
        )

        if not isinstance(
            values,
            tuple,
        ):

            raise TypeError(
                "kinds must be a tuple or None."
            )

        if not values:

            raise ValueError(
                "At least one conclusion kind is required."
            )

        normalized: list[
            InvestigationRAGConclusionKind
        ] = []

        seen: set[
            InvestigationRAGConclusionKind
        ] = set()

        for kind in values:

            if not isinstance(
                kind,
                InvestigationRAGConclusionKind,
            ):

                raise TypeError(
                    "Every conclusion kind must be "
                    "InvestigationRAGConclusionKind."
                )

            if kind in seen:

                continue

            seen.add(
                kind
            )

            normalized.append(
                kind
            )

        return tuple(
            normalized
        )
