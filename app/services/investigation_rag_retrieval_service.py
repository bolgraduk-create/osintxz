"""
Investigation RAG retrieval service.

This module connects the AI / RAG investigation layer
to the existing Unified Search Core.

Architecture:

Investigation question
        ↓
InvestigationRAGRetrievalService
        ↓
InvestigationSearchQuery
        ↓
UnifiedSearchService
        ↓
final ranked InvestigationSearchHit objects
        ↓
stable RAG retrieval sources

Responsibilities:

- create case-scoped investigation search requests
- delegate all retrieval to UnifiedSearchService
- preserve final Unified Search ordering
- preserve object identity and provenance
- expose stable source references for later context building
- expose retrieval diagnostics without changing their meaning

Does NOT:

- implement its own search
- calculate embeddings
- perform vector search directly
- rerank results independently
- build LLM prompts
- call Ollama
- create AI conclusions
- create evidence
- change evidence confidence
- perform Entity Resolution
- write to the database

Important boundaries:

RAG retrieval score != Evidence confidence
RAG retrieval score != identity confidence
RAG retrieved source != verified fact
RAG retrieval != grounded citation layer

Grounded citation rendering is implemented later in Block 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from uuid import UUID

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)
from app.investigation.search_result import (
    InvestigationSearchHit,
)
from app.services.unified_search_service import (
    UnifiedSearchService,
)
from app.services.investigation_evidence_confidence_search_enrichment_service import (
    CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY,
    InvestigationEvidenceConfidenceSearchEnrichmentService,
)


# ==========================================================
# Constants
# ==========================================================

DEFAULT_RAG_RESULT_LIMIT = 20

DEFAULT_RAG_CANDIDATE_LIMIT = 100


# ==========================================================
# Match reason contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGMatchReason:
    """
    One preserved search-match explanation.

    This is search provenance only.

    It is NOT evidence confidence and does not assert
    that the underlying information is true.
    """

    reason: str

    method: str | None = None

    score: float | None = None

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )


# ==========================================================
# Retrieved source contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGSource:
    """
    One source selected by Unified Search for RAG use.

    reference_id:
        Stable position-local reference such as R1, R2, R3.

        This is intentionally NOT yet a final grounded
        evidence citation. The grounded citation layer
        is a later Block 9 component.

    object_id / object_type:
        Canonical investigation object identity.

    source:
        Original opaque source object preserved from the
        InvestigationSearchHit. Later Context Builder logic
        may inspect it without RAG retrieval duplicating
        domain-specific extraction rules.
    """

    reference_id: str

    object_id: UUID

    object_type: str

    case_id: UUID | None

    title: str

    snippet: str

    final_score: float

    confidence: float | None

    matched_methods: tuple[
        str,
        ...,
    ]

    reasons: tuple[
        InvestigationRAGMatchReason,
        ...,
    ]

    scores: dict[
        str,
        float,
    ]

    metadata: dict[
        str,
        Any,
    ]

    source: Any | None = None

    # ======================================================
    # Identity helpers
    # ======================================================

    @property
    def source_key(
        self,
    ) -> str:
        """
        Return stable investigation-object key.
        """

        return (
            f"{self.object_type}:"
            f"{self.object_id}"
        )


# ==========================================================
# Retrieval result contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGRetrievalResult:
    """
    Result of one RAG retrieval operation.

    The result deliberately contains retrieved sources only.

    It does not contain:
    - assembled LLM context
    - prompt
    - model response
    - conclusions
    - final grounded citations
    """

    question: str

    case_id: UUID

    sources: tuple[
        InvestigationRAGSource,
        ...,
    ]

    total_matches: int

    candidate_count: int

    duration_seconds: float

    search_metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    warnings: tuple[
        str,
        ...,
    ] = ()

    errors: tuple[
        str,
        ...,
    ] = ()

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def has_sources(
        self,
    ) -> bool:
        """
        Whether retrieval produced at least one source.
        """

        return bool(
            self.sources
        )

    @property
    def source_count(
        self,
    ) -> int:
        """
        Number of sources exposed to the next RAG stage.
        """

        return len(
            self.sources
        )

    @property
    def successful(
        self,
    ) -> bool:
        """
        Retrieval completed without recorded search errors.

        Empty results may still be a successful retrieval.
        """

        return not self.errors


# ==========================================================
# Service
# ==========================================================


class InvestigationRAGRetrievalService:
    """
    Stable RAG retrieval facade over UnifiedSearchService.

    All ranking and retrieval decisions remain owned by
    Unified Search.
    """

    def __init__(
        self,
        *,
        unified_search_service: UnifiedSearchService,
        evidence_confidence_enrichment_service: (
            InvestigationEvidenceConfidenceSearchEnrichmentService
            | None
        ) = None,
    ) -> None:

        if unified_search_service is None:

            raise ValueError(
                "unified_search_service is required."
            )

        self.unified_search_service = (
            unified_search_service
        )

        self.evidence_confidence_enrichment_service = (
            evidence_confidence_enrichment_service
            or InvestigationEvidenceConfidenceSearchEnrichmentService()
        )

    # ======================================================
    # Public retrieval API
    # ======================================================

    def retrieve(
        self,
        *,
        question: str,
        case_id: UUID,
        limit: int = DEFAULT_RAG_RESULT_LIMIT,
        candidate_limit: int = (
            DEFAULT_RAG_CANDIDATE_LIMIT
        ),
        object_types: tuple[
            str,
            ...,
        ] = (),
        object_ids: tuple[
            UUID,
            ...,
        ] = (),
        minimum_score: float = 0.0,
        include_deleted: bool = False,
        enable_query_expansion: bool = True,
        enable_reranking: bool = True,
        enable_neural_reranking: bool = True,
        metadata: dict[
            str,
            Any,
        ]
        | None = None,
        evidence_confidence_results: tuple[
            object,
            ...,
        ] = (),
    ) -> InvestigationRAGRetrievalResult:
        """
        Retrieve ranked investigation sources for one question.

        The request is always case-scoped.

        SearchMethod.AUTO is used deliberately so RAG benefits
        from every appropriate retriever already registered in
        UnifiedSearchService.
        """

        normalized_question = (
            self._normalize_question(
                question
            )
        )

        normalized_case_id = (
            self._normalize_uuid(
                case_id,
                field_name="case_id",
            )
        )

        query_metadata = dict(
            metadata
            or {}
        )

        query_metadata.update(
            {
                "consumer": (
                    "investigation_rag"
                ),
                "rag_stage": (
                    "retrieval"
                ),
            }
        )

        query = InvestigationSearchQuery(
            query=normalized_question,

            case_id=normalized_case_id,

            object_types=tuple(
                object_types
            ),

            object_ids=tuple(
                object_ids
            ),

            methods=(
                SearchMethod.AUTO,
            ),

            limit=limit,

            candidate_limit=(
                candidate_limit
            ),

            minimum_score=(
                minimum_score
            ),

            include_deleted=(
                include_deleted
            ),

            enable_query_expansion=(
                enable_query_expansion
            ),

            enable_reranking=(
                enable_reranking
            ),

            source_object_id=None,

            source_object_type=None,

            metadata=query_metadata,

            enable_neural_reranking=(
                enable_neural_reranking
            ),
        )

        return self.retrieve_query(
            query,
            evidence_confidence_results=(
                evidence_confidence_results
            ),
        )

    def retrieve_query(
        self,
        query: InvestigationSearchQuery,
        *,
        evidence_confidence_results: tuple[
            object,
            ...,
        ] = (),
    ) -> InvestigationRAGRetrievalResult:
        """
        Execute an already-created investigation search query
        and convert its final Unified Search hits to RAG sources.

        This method exists so later AI services may create a
        richer InvestigationSearchQuery without bypassing the
        same RAG retrieval contract.
        """

        if not isinstance(
            query,
            InvestigationSearchQuery,
        ):

            raise TypeError(
                "query must be InvestigationSearchQuery."
            )

        if query.case_id is None:

            raise ValueError(
                "RAG retrieval requires case_id."
            )

        if not query.has_text_query:

            raise ValueError(
                "RAG retrieval requires a textual question."
            )

        response = (
            self.unified_search_service
            .search(
                query
            )
        )

        self.evidence_confidence_enrichment_service.annotate(
            response.hits,
            evidence_confidence_results,
        )

        enriched_hit_count = sum(
            1
            for hit in response.hits
            if (
                CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY
                in hit.metadata
            )
        )

        response.metadata[
            "canonical_evidence_confidence"
        ] = {
            "enabled": bool(
                evidence_confidence_results
            ),
            "applied_hit_count": enriched_hit_count,
            "proposition_count": len(
                evidence_confidence_results
            ),
            "ranking_changed": False,
        }

        sources = tuple(
            self._build_source(
                hit=hit,
                position=position,
            )
            for position, hit
            in enumerate(
                response.hits,
                start=1,
            )
        )

        return InvestigationRAGRetrievalResult(
            question=query.query,

            case_id=query.case_id,

            sources=sources,

            total_matches=int(
                getattr(
                    response,
                    "total_matches",
                    len(
                        sources
                    ),
                )
            ),

            candidate_count=int(
                getattr(
                    response,
                    "candidate_count",
                    len(
                        sources
                    ),
                )
            ),

            duration_seconds=float(
                getattr(
                    response,
                    "duration_seconds",
                    0.0,
                )
                or 0.0
            ),

            search_metadata=dict(
                getattr(
                    response,
                    "metadata",
                    {},
                )
                or {}
            ),

            warnings=self._normalize_messages(
                getattr(
                    response,
                    "warnings",
                    (),
                )
            ),

            errors=self._normalize_messages(
                getattr(
                    response,
                    "errors",
                    (),
                )
            ),
        )

    # ======================================================
    # Hit conversion
    # ======================================================

    def _build_source(
        self,
        *,
        hit: InvestigationSearchHit,
        position: int,
    ) -> InvestigationRAGSource:
        """
        Convert one final Unified Search hit.

        No new ranking is performed here.

        Position is the final ordering already decided by
        UnifiedSearchService.
        """

        if not isinstance(
            hit,
            InvestigationSearchHit,
        ):

            raise TypeError(
                "RAG source must originate from "
                "InvestigationSearchHit."
            )

        reasons = tuple(
            self._build_reason(
                reason
            )
            for reason in hit.reasons
        )

        methods = tuple(
            self._method_name(
                method
            )
            for method in (
                hit.matched_methods
            )
        )

        return InvestigationRAGSource(
            reference_id=(
                f"R{position}"
            ),

            object_id=hit.object_id,

            object_type=(
                hit.object_type
            ),

            case_id=hit.case_id,

            title=(
                hit.title
                or ""
            ),

            snippet=(
                hit.snippet
                or ""
            ),

            final_score=float(
                hit.final_score
            ),

            confidence=(
                float(
                    hit.confidence
                )
                if (
                    hit.confidence
                    is not None
                )
                else None
            ),

            matched_methods=methods,

            reasons=reasons,

            scores=(
                self._extract_scores(
                    hit
                )
            ),

            metadata=dict(
                hit.metadata
                or {}
            ),

            source=hit.source,
        )

    @staticmethod
    def _build_reason(
        reason,
    ) -> InvestigationRAGMatchReason:
        """
        Preserve one SearchMatchReason without interpreting it.
        """

        method = getattr(
            reason,
            "method",
            None,
        )

        score = getattr(
            reason,
            "score",
            None,
        )

        return InvestigationRAGMatchReason(
            reason=str(
                getattr(
                    reason,
                    "reason",
                    "",
                )
            ).strip(),

            method=(
                InvestigationRAGRetrievalService
                ._method_name(
                    method
                )
                if method is not None
                else None
            ),

            score=(
                float(
                    score
                )
                if score is not None
                else None
            ),

            details=dict(
                getattr(
                    reason,
                    "details",
                    {},
                )
                or {}
            ),
        )

    # ======================================================
    # Score preservation
    # ======================================================

    @staticmethod
    def _extract_scores(
        hit: InvestigationSearchHit,
    ) -> dict[
        str,
        float,
    ]:
        """
        Preserve available SearchScores values.

        These values retain their original search meaning.
        They are not converted into evidence confidence.
        """

        scores = getattr(
            hit,
            "scores",
            None,
        )

        if scores is None:

            return {}

        field_names = (
            "structured",
            "lexical",
            "fuzzy",
            "semantic",
            "image",
            "graph",
            "temporal",
            "anomaly",
            "evidence",
            "confidence",
            "rerank",
            "final",
        )

        result: dict[
            str,
            float,
        ] = {}

        for field_name in field_names:

            value = getattr(
                scores,
                field_name,
                None,
            )

            if value is None:

                continue

            try:

                result[
                    field_name
                ] = float(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

        return result

    # ======================================================
    # Normalization
    # ======================================================

    @staticmethod
    def _normalize_question(
        value: str,
    ) -> str:
        """
        Normalize and validate investigation question.
        """

        if not isinstance(
            value,
            str,
        ):

            raise TypeError(
                "question must be a string."
            )

        normalized = (
            value.strip()
        )

        if not normalized:

            raise ValueError(
                "question cannot be empty."
            )

        return normalized

    @staticmethod
    def _normalize_uuid(
        value: UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Normalize UUID-compatible identifier.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must be a valid UUID."
            ) from error

    @staticmethod
    def _method_name(
        method,
    ) -> str:
        """
        Normalize SearchMethod-like value.
        """

        value = getattr(
            method,
            "value",
            method,
        )

        return str(
            value
        ).strip()

    @staticmethod
    def _normalize_messages(
        values,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Normalize warning/error collections.
        """

        if values is None:

            return ()

        if isinstance(
            values,
            str,
        ):

            values = (
                values,
            )

        return tuple(
            message
            for message in (
                str(
                    value
                ).strip()
                for value in values
            )
            if message
        )