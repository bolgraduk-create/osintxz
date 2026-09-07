"""
Search result diversification service.

Reorders already ranked investigation search results so
redundant groups do not dominate the top of the result
list.

Architecture:

Ranked hits
    ↓
SearchResultGroupingService
    ↓
redundancy groups
    ↓
SearchResultDiversificationService
    ↓
diversified ordering

The service is deliberately non-destructive.

It does NOT:

- delete hits
- merge objects
- modify retrieval scores
- modify fusion scores
- modify rerank scores
- modify final scores
- perform Entity Resolution
- calculate evidence confidence

Instead, it calculates a temporary diversity priority used
only for ordering.

This is important because:

    relevance
        ≠
    novelty
        ≠
    identity confidence
        ≠
    evidence confidence

A highly relevant result remains highly relevant even when
it is moved lower because many equivalent contextual
results have already been shown.
"""

from __future__ import annotations


from dataclasses import dataclass
from math import isfinite


from app.investigation.search_result import (
    InvestigationSearchHit,
)

from app.services.search_result_grouping_service import (
    SearchResultGroupingService,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchResultDiversificationConfig:
    """
    Diversification configuration.

    maximum_candidates:
        Only the strongest mathematical/neural candidate
        window is diversified.

    context_repeat_penalty:
        Controls how quickly repeated context_match
        results lose temporary ordering priority.

    near_duplicate_repeat_penalty:
        Stronger penalty for repeated near-duplicate
        content.

    minimum_novelty:
        Lower bound for novelty factor. Results are never
        removed completely from consideration.

    Penalty formula:

        novelty =
            1 / (
                1
                +
                penalty
                * already_selected_from_group
            )

    diversity priority:

        final_score
        *
        novelty

    Original final_score remains unchanged.
    """

    maximum_candidates: int = 250

    context_repeat_penalty: float = 1.00

    near_duplicate_repeat_penalty: float = 1.75

    generic_repeat_penalty: float = 0.75

    minimum_novelty: float = 0.05

    def __post_init__(
        self,
    ) -> None:

        if self.maximum_candidates < 1:

            raise ValueError(
                "maximum_candidates must "
                "be at least 1."
            )

        penalties = (
            self.context_repeat_penalty,
            self.near_duplicate_repeat_penalty,
            self.generic_repeat_penalty,
        )

        for penalty in penalties:

            if not isfinite(
                penalty
            ):

                raise ValueError(
                    "Diversification penalties "
                    "must be finite."
                )

            if penalty < 0.0:

                raise ValueError(
                    "Diversification penalties "
                    "cannot be negative."
                )

        if not isfinite(
            self.minimum_novelty
        ):

            raise ValueError(
                "minimum_novelty must "
                "be finite."
            )

        if not (
            0.0
            <
            self.minimum_novelty
            <=
            1.0
        ):

            raise ValueError(
                "minimum_novelty must be "
                "greater than 0.0 and "
                "at most 1.0."
            )


# ==========================================================
# Internal candidate
# ==========================================================


@dataclass(
    slots=True,
)
class _DiversificationCandidate:
    """
    Candidate prepared for iterative diversification.
    """

    hit: InvestigationSearchHit

    original_rank: int

    group_id: str

    group_kind: str

    group_size: int


# ==========================================================
# Service
# ==========================================================


class SearchResultDiversificationService:
    """
    Group-aware non-destructive search diversification.

    The service uses greedy selection.

    At each step:

    1. calculate temporary diversity priority for every
       remaining candidate;

    2. reduce priority when members from the same
       redundancy group were already selected;

    3. choose the strongest remaining candidate.

    This preserves relevance while preventing one repeated
    group from filling the entire Top-N.
    """

    METADATA_KEY = (
        "search_diversification"
    )

    GROUPING_METADATA_KEY = (
        "search_grouping"
    )

    def __init__(
        self,
        config: (
            SearchResultDiversificationConfig
            | None
        ) = None,
        *,
        grouping_service: (
            SearchResultGroupingService
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or SearchResultDiversificationConfig()
        )

        self.grouping_service = (
            grouping_service
            or SearchResultGroupingService()
        )

    # ======================================================
    # Public API
    # ======================================================

    def diversify(
        self,
        hits: list[
            InvestigationSearchHit
        ],
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Return diversified ordering.

        Search scores and object identity remain unchanged.
        """

        if not hits:

            return []

        grouped_hits = (
            self._ensure_grouping(
                hits
            )
        )

        candidates = (
            self._prepare_candidates(
                grouped_hits
            )
        )

        if not candidates:

            return []

        # --------------------------------------------------
        # Restore canonical pre-diversification ordering
        # --------------------------------------------------
        #
        # This makes the service idempotent.
        #
        # Running diversify() again on an already
        # diversified result uses search_grouping's
        # original_rank rather than the current list order.
        # --------------------------------------------------

        candidates.sort(
            key=lambda candidate: (
                candidate.original_rank
            )
        )

        window_size = min(
            self.config.maximum_candidates,
            len(
                candidates
            ),
        )

        window = list(
            candidates[
                :window_size
            ]
        )

        tail = list(
            candidates[
                window_size:
            ]
        )

        # --------------------------------------------------
        # Greedy group-aware ordering
        # --------------------------------------------------

        selected: list[
            _DiversificationCandidate
        ] = []

        group_selected_counts: dict[
            str,
            int,
        ] = {}

        while window:

            best_index = 0

            best_priority = -1.0

            best_original_rank = (
                10**18
            )

            best_novelty = 1.0

            best_previous_count = 0

            for index, candidate in enumerate(
                window
            ):

                previous_count = (
                    group_selected_counts.get(
                        candidate.group_id,
                        0,
                    )
                )

                novelty = (
                    self._novelty_factor(
                        group_kind=(
                            candidate.group_kind
                        ),
                        already_selected=(
                            previous_count
                        ),
                    )
                )

                priority = (
                    self._base_score(
                        candidate.hit
                    )
                    *
                    novelty
                )

                if (
                    priority
                    >
                    best_priority
                ):

                    best_index = index

                    best_priority = (
                        priority
                    )

                    best_original_rank = (
                        candidate.original_rank
                    )

                    best_novelty = (
                        novelty
                    )

                    best_previous_count = (
                        previous_count
                    )

                    continue

                if (
                    priority
                    ==
                    best_priority
                    and
                    candidate.original_rank
                    <
                    best_original_rank
                ):

                    best_index = index

                    best_priority = (
                        priority
                    )

                    best_original_rank = (
                        candidate.original_rank
                    )

                    best_novelty = (
                        novelty
                    )

                    best_previous_count = (
                        previous_count
                    )

            chosen = (
                window.pop(
                    best_index
                )
            )

            group_selected_counts[
                chosen.group_id
            ] = (
                group_selected_counts.get(
                    chosen.group_id,
                    0,
                )
                + 1
            )

            selected.append(
                chosen
            )

            chosen.hit.metadata[
                self.METADATA_KEY
            ] = {
                "applied": True,
                "original_rank": (
                    chosen.original_rank
                ),
                "diversification_score": (
                    self._clamp(
                        best_priority
                    )
                ),
                "novelty_factor": (
                    best_novelty
                ),
                "previous_group_members": (
                    best_previous_count
                ),
                "group_id": (
                    chosen.group_id
                ),
                "group_kind": (
                    chosen.group_kind
                ),
                "group_size": (
                    chosen.group_size
                ),
            }

        # --------------------------------------------------
        # Tail is kept in original order
        # --------------------------------------------------

        for candidate in tail:

            candidate.hit.metadata[
                self.METADATA_KEY
            ] = {
                "applied": False,
                "original_rank": (
                    candidate.original_rank
                ),
                "diversification_score": (
                    self._base_score(
                        candidate.hit
                    )
                ),
                "novelty_factor": 1.0,
                "previous_group_members": None,
                "group_id": (
                    candidate.group_id
                ),
                "group_kind": (
                    candidate.group_kind
                ),
                "group_size": (
                    candidate.group_size
                ),
            }

        diversified_candidates = (
            selected
            + tail
        )

        diversified_hits = [
            candidate.hit
            for candidate
            in diversified_candidates
        ]

        # --------------------------------------------------
        # Final diversified rank metadata
        # --------------------------------------------------

        for rank, hit in enumerate(
            diversified_hits,
            start=1,
        ):

            data = hit.metadata.get(
                self.METADATA_KEY
            )

            if isinstance(
                data,
                dict,
            ):

                data[
                    "diversified_rank"
                ] = rank

        return diversified_hits

    # ======================================================
    # Ensure grouping
    # ======================================================

    def _ensure_grouping(
        self,
        hits: list[
            InvestigationSearchHit
        ],
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Reuse existing grouping metadata when available.

        This is important for idempotency.

        If grouping metadata is missing or incomplete,
        grouping is calculated once.
        """

        if all(
            self._has_valid_grouping(
                hit
            )
            for hit in hits
        ):

            return list(
                hits
            )

        return (
            self.grouping_service.group(
                list(
                    hits
                )
            )
        )

    # ======================================================
    # Candidate preparation
    # ======================================================

    def _prepare_candidates(
        self,
        hits: list[
            InvestigationSearchHit
        ],
    ) -> list[
        _DiversificationCandidate
    ]:
        """
        Convert hits into diversification candidates.
        """

        candidates: list[
            _DiversificationCandidate
        ] = []

        for fallback_rank, hit in enumerate(
            hits,
            start=1,
        ):

            grouping = hit.metadata.get(
                self.GROUPING_METADATA_KEY
            )

            if not isinstance(
                grouping,
                dict,
            ):

                continue

            group_id = grouping.get(
                "group_id"
            )

            group_kind = grouping.get(
                "group_kind"
            )

            group_size = grouping.get(
                "group_size"
            )

            original_rank = grouping.get(
                "original_rank"
            )

            if not isinstance(
                group_id,
                str,
            ):

                continue

            if not isinstance(
                group_kind,
                str,
            ):

                continue

            if not isinstance(
                group_size,
                int,
            ):

                group_size = 1

            if not isinstance(
                original_rank,
                int,
            ):

                original_rank = (
                    fallback_rank
                )

            candidates.append(
                _DiversificationCandidate(
                    hit=hit,
                    original_rank=(
                        original_rank
                    ),
                    group_id=group_id,
                    group_kind=(
                        group_kind
                    ),
                    group_size=max(
                        1,
                        group_size,
                    ),
                )
            )

        return candidates

    # ======================================================
    # Novelty
    # ======================================================

    def _novelty_factor(
        self,
        *,
        group_kind: str,
        already_selected: int,
    ) -> float:
        """
        Calculate temporary novelty multiplier.

        First result from every group always receives 1.0.

        Later members receive progressively smaller
        temporary priority.
        """

        if already_selected <= 0:

            return 1.0

        penalty = (
            self._penalty_for_group_kind(
                group_kind
            )
        )

        if penalty <= 0.0:

            return 1.0

        novelty = (
            1.0
            /
            (
                1.0
                +
                penalty
                * already_selected
            )
        )

        return max(
            self.config.minimum_novelty,
            self._clamp(
                novelty
            ),
        )

    def _penalty_for_group_kind(
        self,
        group_kind: str,
    ) -> float:
        """
        Select repeat penalty by redundancy semantics.
        """

        normalized = (
            group_kind.strip()
            .casefold()
        )

        if (
            normalized
            == "context_match"
        ):

            return (
                self.config
                .context_repeat_penalty
            )

        if (
            normalized
            == "near_duplicate_content"
        ):

            return (
                self.config
                .near_duplicate_repeat_penalty
            )

        if normalized == "unique":

            return 0.0

        return (
            self.config
            .generic_repeat_penalty
        )

    # ======================================================
    # Metadata validation
    # ======================================================

    def _has_valid_grouping(
        self,
        hit: InvestigationSearchHit,
    ) -> bool:
        """
        Check whether hit already has reusable grouping.
        """

        data = hit.metadata.get(
            self.GROUPING_METADATA_KEY
        )

        if not isinstance(
            data,
            dict,
        ):

            return False

        if not isinstance(
            data.get(
                "group_id"
            ),
            str,
        ):

            return False

        if not isinstance(
            data.get(
                "group_kind"
            ),
            str,
        ):

            return False

        if not isinstance(
            data.get(
                "original_rank"
            ),
            int,
        ):

            return False

        return True

    # ======================================================
    # Score
    # ======================================================

    @staticmethod
    def _base_score(
        hit: InvestigationSearchHit,
    ) -> float:
        """
        Use final relevance score without modifying it.
        """

        try:

            value = float(
                hit.final_score
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        return (
            SearchResultDiversificationService
            ._clamp(
                value
            )
        )

    # ======================================================
    # Numerical helper
    # ======================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        """
        Clamp numerical value to 0..1.
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