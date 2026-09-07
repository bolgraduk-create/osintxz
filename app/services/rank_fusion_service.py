"""
Rank fusion for Unified Search.

Combines candidate rankings produced by independent
retrieval mechanisms.

Primary algorithm:

    Reciprocal Rank Fusion (RRF)

Formula:

    score(document) =
        SUM(
            weight(method)
            /
            (k + rank(document, method))
        )

Architecture:

Retriever result lists
        ↓
RankFusionService
        ↓
RRF
        ↓
Fused InvestigationSearchHit[]
        ↓
optional reranking later

Responsibilities:

- combine multiple ranked result lists
- calculate Reciprocal Rank Fusion scores
- support optional method weights
- merge duplicate investigation objects
- preserve retrieval provenance
- produce deterministic fused ordering

Does NOT:

- execute retrieval
- normalize raw retrieval scores
- perform semantic search
- calculate BM25
- perform cross-encoder reranking
- perform analytical enrichment
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from app.investigation.search_query import (
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
)


# ==========================================================
# Fusion configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RankFusionConfig:
    """
    Configuration for Reciprocal Rank Fusion.

    k controls how strongly top positions dominate.

    The classic RRF default is commonly k=60.
    """

    k: int = 60

    def __post_init__(
        self,
    ) -> None:

        if self.k < 1:

            raise ValueError(
                "RRF k must be at least 1."
            )


# ==========================================================
# Rank Fusion Service
# ==========================================================


class RankFusionService:
    """
    Combines independent retrieval rankings using RRF.
    """

    def __init__(
        self,
        config: RankFusionConfig | None = None,
        *,
        method_weights: dict[
            SearchMethod,
            float,
        ]
        | None = None,
    ) -> None:

        self.config = (
            config
            or RankFusionConfig()
        )

        self.method_weights = (
            self._validate_weights(
                method_weights
                or {}
            )
        )

    # ======================================================
    # Public API
    # ======================================================

    def fuse(
        self,
        rankings: dict[
            SearchMethod,
            list[
                InvestigationSearchHit
            ],
        ],
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Fuse several ranked candidate lists.

        Each input list must already be ordered from
        best to worst by its own retrieval mechanism.

        Duplicate objects appearing in multiple lists
        are merged by stable identity.
        """

        if not rankings:

            return []

        merged: dict[
            tuple,
            InvestigationSearchHit,
        ] = {}

        raw_fusion_scores: dict[
            tuple,
            float,
        ] = {}

        # --------------------------------------------------
        # Process each retrieval ranking
        # --------------------------------------------------

        for (
            method,
            hits,
        ) in rankings.items():

            if (
                method
                == SearchMethod.AUTO
            ):

                continue

            weight = self.get_weight(
                method
            )

            seen_in_ranking: set[
                tuple
            ] = set()

            for rank, hit in enumerate(
                hits,
                start=1,
            ):

                if not isinstance(
                    hit,
                    InvestigationSearchHit,
                ):

                    raise TypeError(
                        "Rank fusion accepts only "
                        "InvestigationSearchHit objects."
                    )

                identity = (
                    hit.identity_key
                )

                # A retriever should not gain additional
                # influence by returning the same object
                # several times.
                if (
                    identity
                    in seen_in_ranking
                ):

                    # Duplicate occurrences inside the same
                    # SearchMethod must not gain another RRF
                    # contribution. They may, however, carry
                    # stronger raw retrieval evidence or useful
                    # metadata/reasons from another retriever
                    # implementing the same method.
                    #
                    # Merge that evidence into the already
                    # accepted candidate without changing its
                    # rank contribution.
                    existing = merged.get(
                        identity
                    )

                    if existing is not None:

                        self._merge_hit(
                            target=existing,
                            incoming=hit,
                        )

                        existing.add_method(
                            method
                        )

                    continue

                seen_in_ranking.add(
                    identity
                )

                contribution = (
                    weight
                    / (
                        self.config.k
                        + rank
                    )
                )

                raw_fusion_scores[
                    identity
                ] = (
                    raw_fusion_scores.get(
                        identity,
                        0.0,
                    )
                    + contribution
                )

                existing = merged.get(
                    identity
                )

                if existing is None:

                    merged[
                        identity
                    ] = hit

                else:

                    self._merge_hit(
                        target=existing,
                        incoming=hit,
                    )

                merged[
                    identity
                ].add_method(
                    method
                )

        if not merged:

            return []

        # --------------------------------------------------
        # Normalize RRF scores
        # --------------------------------------------------

        maximum_score = max(
            raw_fusion_scores.values()
        )

        for (
            identity,
            hit,
        ) in merged.items():

            raw_score = (
                raw_fusion_scores[
                    identity
                ]
            )

            if maximum_score > 0.0:

                normalized_score = (
                    raw_score
                    / maximum_score
                )

            else:

                normalized_score = 0.0

            normalized_score = min(
                1.0,
                max(
                    0.0,
                    normalized_score,
                ),
            )

            hit.scores.fusion = (
                normalized_score
            )

            hit.scores.final = (
                normalized_score
            )

            hit.metadata[
                "rrf_raw_score"
            ] = raw_score

            hit.metadata[
                "rrf_score"
            ] = normalized_score

        # --------------------------------------------------
        # Final fused ordering
        # --------------------------------------------------

        fused = list(
            merged.values()
        )

        fused.sort(
            key=lambda hit: (
                -hit.final_score,
                str(
                    hit.object_id
                ),
            )
        )

        return fused

    # ======================================================
    # Weights
    # ======================================================

    def get_weight(
        self,
        method: SearchMethod,
    ) -> float:
        """
        Return configured method weight.

        Unspecified methods have neutral weight 1.0.
        """

        return self.method_weights.get(
            method,
            1.0,
        )

    def _validate_weights(
        self,
        weights: dict[
            SearchMethod,
            float,
        ],
    ) -> dict[
        SearchMethod,
        float,
    ]:
        """
        Validate optional method weights.
        """

        validated: dict[
            SearchMethod,
            float,
        ] = {}

        for (
            method,
            weight,
        ) in weights.items():

            if not isinstance(
                method,
                SearchMethod,
            ):

                raise TypeError(
                    "Rank fusion weight keys must "
                    "be SearchMethod values."
                )

            if (
                method
                == SearchMethod.AUTO
            ):

                raise ValueError(
                    "SearchMethod.AUTO cannot have "
                    "a rank fusion weight."
                )

            try:

                numeric_weight = float(
                    weight
                )

            except (
                TypeError,
                ValueError,
            ) as error:

                raise ValueError(
                    "Rank fusion weight must "
                    "be numeric."
                ) from error

            if not isfinite(
                numeric_weight
            ):

                raise ValueError(
                    "Rank fusion weight must "
                    "be finite."
                )

            if numeric_weight <= 0.0:

                raise ValueError(
                    "Rank fusion weight must "
                    "be greater than zero."
                )

            validated[
                method
            ] = numeric_weight

        return validated

    # ======================================================
    # Candidate merging
    # ======================================================

    def _merge_hit(
        self,
        *,
        target: InvestigationSearchHit,
        incoming: InvestigationSearchHit,
    ) -> None:
        """
        Merge duplicate candidate information.

        The fusion service intentionally preserves all
        useful retrieval evidence.
        """

        # --------------------------------------------------
        # Presentation data
        # --------------------------------------------------

        if (
            not target.title
            and incoming.title
        ):

            target.title = (
                incoming.title
            )

        if (
            not target.snippet
            and incoming.snippet
        ):

            target.snippet = (
                incoming.snippet
            )

        if (
            target.source is None
            and incoming.source is not None
        ):

            target.source = (
                incoming.source
            )

        # --------------------------------------------------
        # Methods
        # --------------------------------------------------

        for method in (
            incoming.matched_methods
        ):

            target.add_method(
                method
            )

        # --------------------------------------------------
        # Reasons
        # --------------------------------------------------

        for reason in incoming.reasons:

            if not self._contains_reason(
                target,
                reason,
            ):

                target.add_reason(
                    reason
                )

        # --------------------------------------------------
        # Retrieval and analytical scores
        # --------------------------------------------------

        self._merge_scores(
            target,
            incoming,
        )

        # --------------------------------------------------
        # Metadata
        # --------------------------------------------------

        for (
            key,
            value,
        ) in incoming.metadata.items():

            if key not in target.metadata:

                target.metadata[
                    key
                ] = value

    # ======================================================
    # Score merging
    # ======================================================

    @staticmethod
    def _merge_scores(
        target: InvestigationSearchHit,
        incoming: InvestigationSearchHit,
    ) -> None:
        """
        Preserve strongest available score of each type.

        Fusion score itself is calculated only after
        all rankings have been processed.
        """

        fields = (
            "structured",
            "lexical",
            "fuzzy",
            "semantic",
            "image",
            "rerank",
            "entity",
            "graph",
            "temporal",
            "anomaly",
            "evidence",
            "confidence",
        )

        for field_name in fields:

            current = getattr(
                target.scores,
                field_name,
            )

            incoming_value = getattr(
                incoming.scores,
                field_name,
            )

            if incoming_value is None:

                continue

            if (
                current is None
                or incoming_value > current
            ):

                setattr(
                    target.scores,
                    field_name,
                    incoming_value,
                )

    # ======================================================
    # Reason helpers
    # ======================================================

    @staticmethod
    def _contains_reason(
        hit: InvestigationSearchHit,
        incoming: SearchMatchReason,
    ) -> bool:
        """
        Check whether equivalent match reason
        already exists.
        """

        for reason in hit.reasons:

            if (
                reason.reason
                == incoming.reason
                and reason.method
                == incoming.method
                and reason.score
                == incoming.score
            ):

                return True

        return False