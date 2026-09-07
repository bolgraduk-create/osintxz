"""
Unified investigation search result contracts.

Defines the common output format used by all
investigation search mechanisms.

Architecture:

Retrievers
    ├── structured
    ├── lexical
    ├── fuzzy
    ├── semantic
    └── image
        ↓
InvestigationSearchHit
        ↓
Fusion / Ranking
        ↓
Analytical enrichment
        ↓
InvestigationSearchResponse

Responsibilities:

- represent one search candidate
- store independent search scores
- preserve match provenance
- store explanations for why an object matched
- provide one final normalized score
- represent the final unified search response

Does NOT:

- execute searches
- access repositories
- calculate embeddings
- perform graph analysis
- perform UI rendering
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


# ==========================================================
# Score helpers
# ==========================================================


def _validate_score(
    value: float | None,
    field_name: str,
) -> float | None:
    """
    Validate a normalized score.

    All unified search scores use the 0.0-1.0 range.

    Individual adapters are responsible for converting
    source-specific scales before creating a search hit.

    Example:

        image similarity 87.5%
            ↓
        0.875
    """

    if value is None:
        return None

    try:

        normalized = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise ValueError(
            f"{field_name} must be numeric."
        ) from error

    if not (
        0.0
        <= normalized
        <= 1.0
    ):

        raise ValueError(
            f"{field_name} must be between "
            "0.0 and 1.0."
        )

    return normalized


# ==========================================================
# Search scores
# ==========================================================


@dataclass(slots=True)
class SearchScores:
    """
    Independent normalized signals attached
    to one investigation search result.

    Retrieval scores describe how the object
    was found.

    Analytical scores are added later by the
    Investigation Engine.

    All values use the 0.0-1.0 range.
    """

    # ======================================================
    # Retrieval
    # ======================================================

    structured: float | None = None

    lexical: float | None = None

    fuzzy: float | None = None

    semantic: float | None = None

    image: float | None = None

    # ======================================================
    # Search pipeline
    # ======================================================

    fusion: float | None = None

    rerank: float | None = None

    # ======================================================
    # Analytical enrichment
    # ======================================================

    entity: float | None = None

    graph: float | None = None

    temporal: float | None = None

    anomaly: float | None = None

    evidence: float | None = None

    # ======================================================
    # Final evaluation
    # ======================================================

    confidence: float | None = None

    final: float = 0.0

    # ======================================================
    # Validation
    # ======================================================

    def __post_init__(
        self,
    ) -> None:
        """
        Validate every score.
        """

        self.structured = _validate_score(
            self.structured,
            "structured",
        )

        self.lexical = _validate_score(
            self.lexical,
            "lexical",
        )

        self.fuzzy = _validate_score(
            self.fuzzy,
            "fuzzy",
        )

        self.semantic = _validate_score(
            self.semantic,
            "semantic",
        )

        self.image = _validate_score(
            self.image,
            "image",
        )

        self.fusion = _validate_score(
            self.fusion,
            "fusion",
        )

        self.rerank = _validate_score(
            self.rerank,
            "rerank",
        )

        self.entity = _validate_score(
            self.entity,
            "entity",
        )

        self.graph = _validate_score(
            self.graph,
            "graph",
        )

        self.temporal = _validate_score(
            self.temporal,
            "temporal",
        )

        self.anomaly = _validate_score(
            self.anomaly,
            "anomaly",
        )

        self.evidence = _validate_score(
            self.evidence,
            "evidence",
        )

        self.confidence = _validate_score(
            self.confidence,
            "confidence",
        )

        validated_final = _validate_score(
            self.final,
            "final",
        )

        self.final = (
            validated_final
            if validated_final is not None
            else 0.0
        )

    # ======================================================
    # Helpers
    # ======================================================

    def retrieval_scores(
        self,
    ) -> dict[str, float]:
        """
        Return only available retrieval scores.
        """

        values = {
            "structured": self.structured,
            "lexical": self.lexical,
            "fuzzy": self.fuzzy,
            "semantic": self.semantic,
            "image": self.image,
        }

        return {
            name: value
            for name, value
            in values.items()
            if value is not None
        }

    def analytical_scores(
        self,
    ) -> dict[str, float]:
        """
        Return only available analytical scores.
        """

        values = {
            "entity": self.entity,
            "graph": self.graph,
            "temporal": self.temporal,
            "anomaly": self.anomaly,
            "evidence": self.evidence,
        }

        return {
            name: value
            for name, value
            in values.items()
            if value is not None
        }

    def available_scores(
        self,
    ) -> dict[str, float]:
        """
        Return every currently available score.
        """

        values = {
            **self.retrieval_scores(),
            "fusion": self.fusion,
            "rerank": self.rerank,
            **self.analytical_scores(),
            "confidence": self.confidence,
            "final": self.final,
        }

        return {
            name: value
            for name, value
            in values.items()
            if value is not None
        }


# ==========================================================
# Match explanation
# ==========================================================


@dataclass(slots=True)
class SearchMatchReason:
    """
    Human-readable explanation of one signal
    that contributed to a search result.

    Examples:

    - exact email match
    - similar username
    - semantic text similarity
    - visually similar image
    - shared graph neighbour
    """

    reason: str

    method: SearchMethod | None = None

    score: float | None = None

    details: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        """
        Normalize explanation fields.
        """

        self.reason = self.reason.strip()

        if not self.reason:

            raise ValueError(
                "Search match reason cannot be empty."
            )

        self.score = _validate_score(
            self.score,
            "reason score",
        )

        if (
            self.method is not None
            and not isinstance(
                self.method,
                SearchMethod,
            )
        ):

            self.method = SearchMethod(
                self.method
            )


# ==========================================================
# Search hit
# ==========================================================


@dataclass(slots=True)
class InvestigationSearchHit:
    """
    One unified search candidate.

    Every retriever must eventually convert its own
    result into this representation.

    The object may later receive additional scores
    from fusion, reranking and analytical stages.
    """

    # ======================================================
    # Identity
    # ======================================================

    object_id: UUID

    object_type: str

    case_id: UUID | None = None

    # ======================================================
    # Presentation
    # ======================================================

    title: str = ""

    snippet: str = ""

    # ======================================================
    # Scoring
    # ======================================================

    scores: SearchScores = field(
        default_factory=SearchScores
    )

    # ======================================================
    # Provenance
    # ======================================================

    matched_methods: list[
        SearchMethod
    ] = field(
        default_factory=list
    )

    reasons: list[
        SearchMatchReason
    ] = field(
        default_factory=list
    )

    # ======================================================
    # Source data
    # ======================================================

    source: Any | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ======================================================
    # Validation
    # ======================================================

    def __post_init__(
        self,
    ) -> None:
        """
        Normalize hit fields.
        """

        self.object_type = (
            self.object_type
            .strip()
            .lower()
        )

        if not self.object_type:

            raise ValueError(
                "Search result object_type "
                "cannot be empty."
            )

        self.title = self.title.strip()

        self.snippet = self.snippet.strip()

        self.matched_methods = (
            self._normalize_methods(
                self.matched_methods
            )
        )

    # ======================================================
    # Ranking
    # ======================================================

    @property
    def final_score(
        self,
    ) -> float:
        """
        Score used for final ordering.
        """

        return self.scores.final

    @property
    def confidence(
        self,
    ) -> float | None:
        """
        Final confidence value when available.
        """

        return self.scores.confidence

    # ======================================================
    # Provenance helpers
    # ======================================================

    def add_method(
        self,
        method: SearchMethod,
    ) -> None:
        """
        Record that a retriever matched this object.
        """

        if not isinstance(
            method,
            SearchMethod,
        ):

            method = SearchMethod(
                method
            )

        if method not in self.matched_methods:

            self.matched_methods.append(
                method
            )

    def add_reason(
        self,
        reason: SearchMatchReason,
    ) -> None:
        """
        Add one explanation for the match.
        """

        self.reasons.append(
            reason
        )

        if reason.method is not None:

            self.add_method(
                reason.method
            )

    # ======================================================
    # Identity helpers
    # ======================================================

    @property
    def identity_key(
        self,
    ) -> tuple[
        UUID | None,
        str,
        UUID,
    ]:
        """
        Stable identity used when merging candidates
        from multiple retrievers.
        """

        return (
            self.case_id,
            self.object_type,
            self.object_id,
        )

    # ======================================================
    # Internal helpers
    # ======================================================

    @staticmethod
    def _normalize_methods(
        methods: list[
            SearchMethod
        ],
    ) -> list[
        SearchMethod
    ]:
        """
        Normalize retriever provenance.
        """

        normalized: list[
            SearchMethod
        ] = []

        for method in methods:

            if not isinstance(
                method,
                SearchMethod,
            ):

                method = SearchMethod(
                    method
                )

            if (
                method
                == SearchMethod.AUTO
            ):

                continue

            if method not in normalized:

                normalized.append(
                    method
                )

        return normalized


# ==========================================================
# Search response
# ==========================================================


@dataclass(slots=True)
class InvestigationSearchResponse:
    """
    Final response returned by UnifiedSearchService.

    Contains one ranked result collection regardless
    of how many retrieval mechanisms participated.
    """

    # ======================================================
    # Request
    # ======================================================

    query: InvestigationSearchQuery

    # ======================================================
    # Results
    # ======================================================

    hits: list[
        InvestigationSearchHit
    ] = field(
        default_factory=list
    )

    # ======================================================
    # Statistics
    # ======================================================

    candidate_count: int = 0

    total_matches: int = 0

    # ======================================================
    # Runtime
    # ======================================================

    duration_seconds: float = 0.0

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ======================================================
    # Validation
    # ======================================================

    def __post_init__(
        self,
    ) -> None:
        """
        Normalize response statistics.
        """

        if self.candidate_count < 0:

            raise ValueError(
                "candidate_count cannot "
                "be negative."
            )

        if self.total_matches < 0:

            raise ValueError(
                "total_matches cannot "
                "be negative."
            )

        if self.duration_seconds < 0:

            raise ValueError(
                "duration_seconds cannot "
                "be negative."
            )

    # ======================================================
    # Result helpers
    # ======================================================

    @property
    def returned_count(
        self,
    ) -> int:
        """
        Number of results actually returned.
        """

        return len(
            self.hits
        )

    @property
    def has_results(
        self,
    ) -> bool:
        """
        Whether search returned at least one hit.
        """

        return bool(
            self.hits
        )

    @property
    def has_errors(
        self,
    ) -> bool:
        """
        Whether search produced errors.
        """

        return bool(
            self.errors
        )

    @property
    def has_warnings(
        self,
    ) -> bool:
        """
        Whether search produced warnings.
        """

        return bool(
            self.warnings
        )

    # ======================================================
    # Ordering
    # ======================================================

    def sort_hits(
        self,
    ) -> None:
        """
        Sort results by final score.

        This is the common final ordering operation.
        """

        self.hits.sort(
            key=lambda hit: (
                hit.final_score,
                hit.confidence
                if hit.confidence is not None
                else 0.0,
            ),
            reverse=True,
        )

    def apply_limit(
        self,
    ) -> None:
        """
        Apply result limit from the original request.
        """

        self.hits = self.hits[
            :self.query.limit
        ]

    # ======================================================
    # Runtime helpers
    # ======================================================

    def add_warning(
        self,
        message: str,
    ) -> None:
        """
        Store non-fatal search warning.
        """

        self.warnings.append(
            message
        )

    def add_error(
        self,
        message: str,
    ) -> None:
        """
        Store search error.
        """

        self.errors.append(
            message
        )