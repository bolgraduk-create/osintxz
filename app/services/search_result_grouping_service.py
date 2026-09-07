"""
Search result grouping service.

Annotates ranked investigation search results with
non-destructive redundancy groups.

Architecture:

SearchRankingService
        ↓
ranked InvestigationSearchHit[]
        ↓
SearchResultGroupingService
        ├── contextual redundancy
        ├── exact content repetition
        └── near-duplicate content
        ↓
same InvestigationSearchHit[]
        +
group metadata

Important:

This service does NOT:

- delete results
- merge domain objects
- change search scores
- change final rank
- decide that two entities are the same person
- calculate evidence confidence
- perform OSINT pivoting

Its purpose is to identify search-result redundancy so
a later diversification stage can avoid filling Top-N
with many highly similar results.

This distinction is especially important for future
OSINT workflows:

    several observations of one underlying fact

must not automatically become:

    several independent pieces of evidence
"""

from __future__ import annotations


from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
import re


from app.investigation.search_result import (
    InvestigationSearchHit,
)

from app.services.fuzzy_search_service import (
    FuzzySearchService,
)

from app.services.search_index_field_extractor import (
    SearchIndexFieldExtractor,
    SearchIndexFields,
)


# ==========================================================
# Constants
# ==========================================================


_WORD_PATTERN = re.compile(
    r"\w+",
    flags=re.UNICODE,
)


_CONTEXT_FIELDS = {
    "sender",
    "receiver",
    "chat",
}


_NEAR_DUPLICATE_OBJECT_TYPES = {
    "message",
    "document",
    "evidence",
    "report",
    "note",
}


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchResultGroupingConfig:
    """
    Search redundancy grouping configuration.

    maximum_candidates:
        Only the strongest ranked candidates need costly
        near-duplicate comparison.

    near_duplicate_threshold:
        Minimum content similarity required to place two
        results into the same near-duplicate search group.

    token_weight / trigram_weight:
        Relative contribution of token Jaccard and
        trigram Jaccard.

    These groups describe search redundancy only.
    """

    maximum_candidates: int = 250

    near_duplicate_threshold: float = 0.88

    token_weight: float = 0.65

    trigram_weight: float = 0.35

    def __post_init__(
        self,
    ) -> None:

        if self.maximum_candidates < 1:

            raise ValueError(
                "maximum_candidates must "
                "be at least 1."
            )

        if not (
            0.0
            <= self.near_duplicate_threshold
            <= 1.0
        ):

            raise ValueError(
                "near_duplicate_threshold must "
                "be between 0.0 and 1.0."
            )

        weights = (
            self.token_weight,
            self.trigram_weight,
        )

        for weight in weights:

            if not isfinite(
                weight
            ):

                raise ValueError(
                    "Grouping weights must "
                    "be finite."
                )

            if weight < 0.0:

                raise ValueError(
                    "Grouping weights cannot "
                    "be negative."
                )

        if sum(
            weights
        ) <= 0.0:

            raise ValueError(
                "At least one grouping weight "
                "must be greater than zero."
            )


# ==========================================================
# Internal prepared candidate
# ==========================================================


@dataclass(
    slots=True,
)
class _PreparedHit:
    """
    Search hit prepared for grouping.
    """

    hit: InvestigationSearchHit

    original_rank: int

    fields: SearchIndexFields

    best_field: str | None

    normalized_primary: str

    primary_tokens: set[str]


# ==========================================================
# Internal group representative
# ==========================================================


@dataclass(
    slots=True,
)
class _GroupRepresentative:
    """
    Representative used for near-duplicate comparison.
    """

    group_id: str

    object_type: str

    normalized_text: str

    tokens: set[str]


# ==========================================================
# Assignment
# ==========================================================


@dataclass(
    slots=True,
)
class _GroupingAssignment:
    """
    Internal grouping result for one hit.
    """

    group_id: str

    group_kind: str

    similarity: float

    representative: bool

    original_rank: int

    best_field: str | None


# ==========================================================
# Service
# ==========================================================


class SearchResultGroupingService:
    """
    Non-destructive search result grouping service.

    Search groups are NOT entity-resolution groups and
    are NOT evidence-confidence groups.
    """

    METADATA_KEY = (
        "search_grouping"
    )

    def __init__(
        self,
        config: (
            SearchResultGroupingConfig
            | None
        ) = None,
        *,
        field_extractor: (
            SearchIndexFieldExtractor
            | None
        ) = None,
        fuzzy_search_service: (
            FuzzySearchService
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or SearchResultGroupingConfig()
        )

        self.field_extractor = (
            field_extractor
            or SearchIndexFieldExtractor()
        )

        self.fuzzy_search_service = (
            fuzzy_search_service
            or FuzzySearchService()
        )

    # ======================================================
    # Public API
    # ======================================================

    def group(
        self,
        hits: list[
            InvestigationSearchHit
        ],
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Annotate ranked results with redundancy groups.

        Input order and all scores are preserved.
        """

        if not hits:

            return []

        prepared = [
            self._prepare_hit(
                hit=hit,
                original_rank=rank,
            )
            for rank, hit
            in enumerate(
                hits,
                start=1,
            )
        ]

        assignments: dict[
            tuple,
            _GroupingAssignment,
        ] = {}

        # --------------------------------------------------
        # Deterministic direct groups
        # --------------------------------------------------

        context_groups: dict[
            tuple,
            str,
        ] = {}

        exact_content_groups: dict[
            tuple,
            str,
        ] = {}

        # --------------------------------------------------
        # Representatives for fuzzy near-duplicate groups
        # --------------------------------------------------

        representatives: list[
            _GroupRepresentative
        ] = []

        for index, candidate in enumerate(
            prepared
        ):

            # Expensive near-duplicate grouping is only
            # applied to the strongest ranking window.
            if (
                index
                >= self.config.maximum_candidates
            ):

                assignment = (
                    self._unique_assignment(
                        candidate
                    )
                )

                assignments[
                    candidate.hit.identity_key
                ] = assignment

                continue

            # ----------------------------------------------
            # Contextual redundancy
            # ----------------------------------------------

            context_key = (
                self._context_group_key(
                    candidate
                )
            )

            if context_key is not None:

                group_id = (
                    context_groups.get(
                        context_key
                    )
                )

                is_representative = (
                    group_id is None
                )

                if group_id is None:

                    group_id = (
                        self._stable_group_id(
                            kind="context",
                            value=repr(
                                context_key
                            ),
                        )
                    )

                    context_groups[
                        context_key
                    ] = group_id

                assignments[
                    candidate.hit.identity_key
                ] = _GroupingAssignment(
                    group_id=group_id,
                    group_kind=(
                        "context_match"
                    ),
                    similarity=1.0,
                    representative=(
                        is_representative
                    ),
                    original_rank=(
                        candidate.original_rank
                    ),
                    best_field=(
                        candidate.best_field
                    ),
                )

                continue

            # ----------------------------------------------
            # No meaningful primary representation
            # ----------------------------------------------

            if not candidate.normalized_primary:

                assignments[
                    candidate.hit.identity_key
                ] = (
                    self._unique_assignment(
                        candidate
                    )
                )

                continue

            # ----------------------------------------------
            # Exact repeated content
            # ----------------------------------------------

            exact_key = (
                candidate.hit.object_type,
                candidate.normalized_primary,
            )

            existing_exact_group = (
                exact_content_groups.get(
                    exact_key
                )
            )

            if (
                existing_exact_group
                is not None
            ):

                assignments[
                    candidate.hit.identity_key
                ] = _GroupingAssignment(
                    group_id=(
                        existing_exact_group
                    ),
                    group_kind=(
                        "near_duplicate_content"
                    ),
                    similarity=1.0,
                    representative=False,
                    original_rank=(
                        candidate.original_rank
                    ),
                    best_field=(
                        candidate.best_field
                    ),
                )

                continue

            # ----------------------------------------------
            # Near-duplicate content
            # ----------------------------------------------

            near_duplicate = (
                self._find_near_duplicate_group(
                    candidate=candidate,
                    representatives=(
                        representatives
                    ),
                )
            )

            if near_duplicate is not None:

                (
                    representative,
                    similarity,
                ) = near_duplicate

                assignments[
                    candidate.hit.identity_key
                ] = _GroupingAssignment(
                    group_id=(
                        representative.group_id
                    ),
                    group_kind=(
                        "near_duplicate_content"
                    ),
                    similarity=similarity,
                    representative=False,
                    original_rank=(
                        candidate.original_rank
                    ),
                    best_field=(
                        candidate.best_field
                    ),
                )

                exact_content_groups[
                    exact_key
                ] = (
                    representative.group_id
                )

                continue

            # ----------------------------------------------
            # New content group representative
            # ----------------------------------------------

            group_id = (
                self._stable_group_id(
                    kind="content",
                    value=(
                        candidate.hit.object_type
                        + "|"
                        + candidate.normalized_primary
                    ),
                )
            )

            exact_content_groups[
                exact_key
            ] = group_id

            representatives.append(
                _GroupRepresentative(
                    group_id=group_id,
                    object_type=(
                        candidate.hit.object_type
                    ),
                    normalized_text=(
                        candidate.normalized_primary
                    ),
                    tokens=(
                        candidate.primary_tokens
                    ),
                )
            )

            assignments[
                candidate.hit.identity_key
            ] = _GroupingAssignment(
                group_id=group_id,
                group_kind=(
                    "content_candidate"
                ),
                similarity=1.0,
                representative=True,
                original_rank=(
                    candidate.original_rank
                ),
                best_field=(
                    candidate.best_field
                ),
            )

        # --------------------------------------------------
        # Calculate group sizes
        # --------------------------------------------------

        group_sizes: dict[
            str,
            int,
        ] = {}

        for assignment in (
            assignments.values()
        ):

            group_sizes[
                assignment.group_id
            ] = (
                group_sizes.get(
                    assignment.group_id,
                    0,
                )
                + 1
            )

        # --------------------------------------------------
        # Convert one-member content groups into unique
        # --------------------------------------------------

        for candidate in prepared:

            assignment = assignments[
                candidate.hit.identity_key
            ]

            size = group_sizes[
                assignment.group_id
            ]

            group_kind = (
                assignment.group_kind
            )

            if (
                group_kind
                == "content_candidate"
            ):

                if size > 1:

                    group_kind = (
                        "near_duplicate_content"
                    )

                else:

                    group_kind = "unique"

            candidate.hit.metadata[
                self.METADATA_KEY
            ] = {
                "group_id": (
                    assignment.group_id
                ),
                "group_kind": (
                    group_kind
                ),
                "group_size": size,
                "representative": (
                    assignment.representative
                ),
                "similarity_to_representative": (
                    assignment.similarity
                ),
                "original_rank": (
                    assignment.original_rank
                ),
                "best_field": (
                    assignment.best_field
                ),
            }

        # Ordering remains exactly unchanged.
        return list(
            hits
        )

    # ======================================================
    # Preparation
    # ======================================================

    def _prepare_hit(
        self,
        *,
        hit: InvestigationSearchHit,
        original_rank: int,
    ) -> _PreparedHit:
        """
        Prepare typed fields and primary representation.
        """

        fields = (
            self.field_extractor.extract(
                source=hit.source,
                object_type=(
                    hit.object_type
                ),
                title=hit.title,
                content=hit.snippet,
            )
        )

        best_field = (
            self._best_ranking_field(
                hit
            )
        )

        primary = (
            self._primary_representation(
                hit=hit,
                fields=fields,
            )
        )

        normalized_primary = (
            self._normalize(
                primary
            )
        )

        return _PreparedHit(
            hit=hit,
            original_rank=original_rank,
            fields=fields,
            best_field=best_field,
            normalized_primary=(
                normalized_primary
            ),
            primary_tokens=(
                self._tokens(
                    normalized_primary
                )
            ),
        )

    # ======================================================
    # Context grouping
    # ======================================================

    def _context_group_key(
        self,
        candidate: _PreparedHit,
    ) -> tuple | None:
        """
        Group context-only Message matches separately.

        Example:

            query: Alena

            Message A:
                SENDER = Alena
                no relevant body text

            Message B:
                SENDER = Alena
                no relevant body text

        They are separate messages, not duplicates.

        However, from the perspective of this query they
        represent repeated matches through the same
        contextual field.

        This becomes a context_match group.
        """

        if (
            candidate.hit.object_type
            != "message"
        ):

            return None

        best_field = (
            candidate.best_field
        )

        if (
            best_field
            not in _CONTEXT_FIELDS
        ):

            return None

        value = (
            candidate.fields.first(
                best_field
            )
        )

        normalized_value = (
            self._normalize(
                value
            )
        )

        if not normalized_value:

            return None

        return (
            candidate.hit.object_type,
            best_field,
            normalized_value,
        )

    # ======================================================
    # Near duplicate grouping
    # ======================================================

    def _find_near_duplicate_group(
        self,
        *,
        candidate: _PreparedHit,
        representatives: list[
            _GroupRepresentative
        ],
    ) -> tuple[
        _GroupRepresentative,
        float,
    ] | None:
        """
        Find sufficiently similar primary content.

        Entity names are deliberately excluded from fuzzy
        grouping because two different people may have
        identical or very similar names.

        Entity identity belongs to Entity Resolution.
        """

        if (
            candidate.hit.object_type
            not in _NEAR_DUPLICATE_OBJECT_TYPES
        ):

            return None

        best_match: (
            _GroupRepresentative
            | None
        ) = None

        best_similarity = 0.0

        for representative in (
            representatives
        ):

            if (
                representative.object_type
                != candidate.hit.object_type
            ):

                continue

            similarity = (
                self._content_similarity(
                    left_text=(
                        candidate.normalized_primary
                    ),
                    left_tokens=(
                        candidate.primary_tokens
                    ),
                    right_text=(
                        representative
                        .normalized_text
                    ),
                    right_tokens=(
                        representative.tokens
                    ),
                )
            )

            if (
                similarity
                > best_similarity
            ):

                best_similarity = (
                    similarity
                )

                best_match = (
                    representative
                )

        if (
            best_match is None
            or best_similarity
            < self.config
            .near_duplicate_threshold
        ):

            return None

        return (
            best_match,
            best_similarity,
        )

    # ======================================================
    # Content similarity
    # ======================================================

    def _content_similarity(
        self,
        *,
        left_text: str,
        left_tokens: set[str],
        right_text: str,
        right_tokens: set[str],
    ) -> float:
        """
        Combine token Jaccard and trigram Jaccard.

        This is intentionally symmetric because here we
        compare two result contents, not query coverage.
        """

        if (
            left_text
            == right_text
        ):

            return (
                1.0
                if left_text
                else 0.0
            )

        token_score = (
            self._token_jaccard(
                left_tokens,
                right_tokens,
            )
        )

        trigram_score = (
            self.fuzzy_search_service
            .trigram_similarity(
                left_text,
                right_text,
            )
        )

        total_weight = (
            self.config.token_weight
            + self.config.trigram_weight
        )

        similarity = (
            (
                token_score
                * self.config.token_weight
            )
            +
            (
                trigram_score
                * self.config.trigram_weight
            )
        ) / total_weight

        return self._clamp(
            similarity
        )

    # ======================================================
    # Primary representation
    # ======================================================

    @staticmethod
    def _primary_representation(
        *,
        hit: InvestigationSearchHit,
        fields: SearchIndexFields,
    ) -> str:
        """
        Return content appropriate for redundancy
        comparison.
        """

        if (
            hit.object_type
            == "message"
        ):

            return (
                fields.message_text
            )

        if hit.object_type == "entity":

            # We keep the representation available for
            # metadata, but Entity is excluded from fuzzy
            # grouping by _find_near_duplicate_group().
            return fields.title

        if fields.title:

            return (
                fields.title
                + "\n"
                + fields.raw_content
            ).strip()

        return fields.raw_content

    # ======================================================
    # Ranking metadata
    # ======================================================

    @staticmethod
    def _best_ranking_field(
        hit: InvestigationSearchHit,
    ) -> str | None:
        """
        Read field-aware ranking provenance.
        """

        ranking = hit.metadata.get(
            "mathematical_ranking"
        )

        if not isinstance(
            ranking,
            dict,
        ):

            return None

        field_relevance = (
            ranking.get(
                "field_relevance"
            )
        )

        if not isinstance(
            field_relevance,
            dict,
        ):

            return None

        value = (
            field_relevance.get(
                "best_field"
            )
        )

        if not isinstance(
            value,
            str,
        ):

            return None

        normalized = (
            value.strip()
            .casefold()
        )

        return (
            normalized
            or None
        )

    # ======================================================
    # Unique assignment
    # ======================================================

    def _unique_assignment(
        self,
        candidate: _PreparedHit,
    ) -> _GroupingAssignment:
        """
        Create independent one-result group.
        """

        group_id = (
            self._stable_group_id(
                kind="unique",
                value=repr(
                    candidate
                    .hit
                    .identity_key
                ),
            )
        )

        return _GroupingAssignment(
            group_id=group_id,
            group_kind="unique",
            similarity=1.0,
            representative=True,
            original_rank=(
                candidate.original_rank
            ),
            best_field=(
                candidate.best_field
            ),
        )

    # ======================================================
    # Stable group id
    # ======================================================

    @staticmethod
    def _stable_group_id(
        *,
        kind: str,
        value: str,
    ) -> str:
        """
        Create deterministic compact search group id.

        This is only an internal grouping identifier and
        has no cryptographic/security meaning.
        """

        payload = (
            kind
            + "|"
            + value
        ).encode(
            "utf-8",
            errors="replace",
        )

        digest = (
            sha256(
                payload
            )
            .hexdigest()
            [:16]
        )

        return (
            f"{kind}:{digest}"
        )

    # ======================================================
    # Text helpers
    # ======================================================

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """
        Normalize text for grouping.
        """

        if not value:

            return ""

        return " ".join(
            value
            .casefold()
            .split()
        )

    @staticmethod
    def _tokens(
        value: str,
    ) -> set[str]:
        """
        Return normalized Unicode token set.
        """

        if not value:

            return set()

        return {
            token
            for token
            in _WORD_PATTERN.findall(
                value
            )
            if token
        }

    @staticmethod
    def _token_jaccard(
        left: set[str],
        right: set[str],
    ) -> float:
        """
        Symmetric token Jaccard similarity.
        """

        if (
            not left
            or not right
        ):

            return 0.0

        if left == right:

            return 1.0

        intersection = (
            left
            & right
        )

        union = (
            left
            | right
        )

        if not union:

            return 0.0

        return (
            len(
                intersection
            )
            /
            len(
                union
            )
        )

    # ======================================================
    # Numerical helpers
    # ======================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        """
        Clamp score into 0..1.
        """

        if not isfinite(
            value
        ):

            return 0.0

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )