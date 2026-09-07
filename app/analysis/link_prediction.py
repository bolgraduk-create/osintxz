"""
Structural graph link prediction.

Finds potentially missing Entity relationships using
classic neighborhood-based graph heuristics.

Implemented metrics:

- Common Neighbors
- Jaccard Coefficient
- Adamic-Adar

Responsibilities:

- generate missing-link candidates
- support undirected graph prediction
- support directed two-hop prediction
- avoid existing relationships
- avoid self-link predictions
- prevent parallel-edge inflation
- calculate Common Neighbors
- calculate Jaccard Coefficient
- calculate Adamic-Adar
- provide deterministic rankings

Does NOT:

- query the database
- create Relationship objects
- persist predictions
- treat predictions as confirmed evidence
- calculate weighted link-prediction variants
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from itertools import combinations

from math import (
    isfinite,
    log,
)

from uuid import UUID

from app.analysis.graph_contracts import (
    GraphDirection,
    GraphNeighborMode,
)

from app.analysis.graph_normalization import (
    NormalizedEntityGraph,
)


# ==========================================================
# Metric
# ==========================================================


class LinkPredictionMetric(
    str,
    Enum,
):
    """
    Supported structural prediction metrics.
    """

    COMMON_NEIGHBORS = (
        "common_neighbors"
    )

    JACCARD = "jaccard"

    ADAMIC_ADAR = "adamic_adar"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LinkPredictionConfig:
    """
    Link-prediction configuration.

    minimum_common_neighbors:

        Candidate must have at least this many
        structural common neighbors.

        Default 1 means zero-score node pairs are never
        materialized as predictions.
    """

    minimum_common_neighbors: int = 1

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.minimum_common_neighbors,
                int,
            )
            or
            self.minimum_common_neighbors < 1
        ):

            raise ValueError(
                "minimum_common_neighbors must "
                "be a positive integer."
            )


# ==========================================================
# Candidate
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LinkPredictionCandidate:
    """
    One potential missing Entity relationship.

    For UNDIRECTED graphs:

        source_entity_id / target_entity_id form a
        canonical unordered pair.

    For DIRECTED graphs:

        source_entity_id -> target_entity_id preserves
        prediction orientation.
    """

    source_entity_id: UUID

    target_entity_id: UUID

    common_neighbor_ids: tuple[
        UUID,
        ...,
    ]

    common_neighbors: int

    jaccard: float

    adamic_adar: float

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.source_entity_id,
            UUID,
        ):

            raise TypeError(
                "source_entity_id must be UUID."
            )

        if not isinstance(
            self.target_entity_id,
            UUID,
        ):

            raise TypeError(
                "target_entity_id must be UUID."
            )

        if (
            self.source_entity_id
            ==
            self.target_entity_id
        ):

            raise ValueError(
                "Link prediction cannot target "
                "the same Entity."
            )

        if not isinstance(
            self.common_neighbor_ids,
            tuple,
        ):

            raise TypeError(
                "common_neighbor_ids must "
                "be a tuple."
            )

        normalized_neighbors: list[
            UUID
        ] = []

        seen: set[
            UUID
        ] = set()

        for entity_id in (
            self.common_neighbor_ids
        ):

            if not isinstance(
                entity_id,
                UUID,
            ):

                raise TypeError(
                    "Common neighbor IDs "
                    "must be UUID."
                )

            if entity_id in seen:

                raise ValueError(
                    "Duplicate common neighbor."
                )

            if entity_id in {
                self.source_entity_id,
                self.target_entity_id,
            }:

                raise ValueError(
                    "Prediction endpoints cannot "
                    "be common neighbors."
                )

            seen.add(
                entity_id
            )

            normalized_neighbors.append(
                entity_id
            )

        normalized_neighbors.sort(
            key=str
        )

        object.__setattr__(
            self,
            "common_neighbor_ids",
            tuple(
                normalized_neighbors
            ),
        )

        if (
            not isinstance(
                self.common_neighbors,
                int,
            )
            or
            self.common_neighbors < 0
        ):

            raise ValueError(
                "common_neighbors must be a "
                "non-negative integer."
            )

        if (
            self.common_neighbors
            !=
            len(
                normalized_neighbors
            )
        ):

            raise ValueError(
                "common_neighbors must match "
                "common_neighbor_ids count."
            )

        jaccard = float(
            self.jaccard
        )

        if (
            not isfinite(
                jaccard
            )
            or not (
                0.0
                <= jaccard
                <= 1.0
            )
        ):

            raise ValueError(
                "jaccard must be between "
                "0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "jaccard",
            jaccard,
        )

        adamic_adar = float(
            self.adamic_adar
        )

        if (
            not isfinite(
                adamic_adar
            )
            or adamic_adar < 0.0
        ):

            raise ValueError(
                "adamic_adar must be finite "
                "and non-negative."
            )

        object.__setattr__(
            self,
            "adamic_adar",
            adamic_adar,
        )

    # ==========================================================
    # Metric access
    # ==========================================================

    def metric_value(
        self,
        metric: LinkPredictionMetric,
    ) -> float:
        """
        Return one metric as float.
        """

        if not isinstance(
            metric,
            LinkPredictionMetric,
        ):

            raise TypeError(
                "metric must be "
                "LinkPredictionMetric."
            )

        if (
            metric
            ==
            LinkPredictionMetric
            .COMMON_NEIGHBORS
        ):

            return float(
                self.common_neighbors
            )

        if (
            metric
            ==
            LinkPredictionMetric
            .JACCARD
        ):

            return self.jaccard

        return self.adamic_adar


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LinkPredictionResult:
    """
    Complete structural link-prediction result.
    """

    direction: GraphDirection

    predictions: tuple[
        LinkPredictionCandidate,
        ...,
    ]

    node_count: int

    edge_count: int

    source_edge_count: int

    evaluated_candidate_count: int

    minimum_common_neighbors: int

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.direction,
            GraphDirection,
        ):

            raise TypeError(
                "direction must be "
                "GraphDirection."
            )

        if not isinstance(
            self.predictions,
            tuple,
        ):

            raise TypeError(
                "predictions must be a tuple."
            )

        seen_pairs: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for prediction in self.predictions:

            if not isinstance(
                prediction,
                LinkPredictionCandidate,
            ):

                raise TypeError(
                    "predictions must contain "
                    "LinkPredictionCandidate."
                )

            pair = (
                prediction.source_entity_id,
                prediction.target_entity_id,
            )

            if pair in seen_pairs:

                raise ValueError(
                    "Duplicate link prediction pair."
                )

            seen_pairs.add(
                pair
            )

        for field_name in (
            "node_count",
            "edge_count",
            "source_edge_count",
            "evaluated_candidate_count",
        ):

            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(
                    value,
                    int,
                )
                or value < 0
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a non-negative integer."
                )

        if (
            not isinstance(
                self.minimum_common_neighbors,
                int,
            )
            or
            self.minimum_common_neighbors < 1
        ):

            raise ValueError(
                "minimum_common_neighbors must "
                "be positive."
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def prediction_count(
        self,
    ) -> int:

        return len(
            self.predictions
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> LinkPredictionCandidate:
        """
        Return one prediction.

        UNDIRECTED pair order is normalized.
        DIRECTED pair order is preserved.
        """

        if not isinstance(
            source_entity_id,
            UUID,
        ):

            raise TypeError(
                "source_entity_id must be UUID."
            )

        if not isinstance(
            target_entity_id,
            UUID,
        ):

            raise TypeError(
                "target_entity_id must be UUID."
            )

        if (
            self.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            source_entity_id, target_entity_id = (
                sorted(
                    (
                        source_entity_id,
                        target_entity_id,
                    ),
                    key=str,
                )
            )

        for prediction in self.predictions:

            if (
                prediction.source_entity_id
                ==
                source_entity_id
                and
                prediction.target_entity_id
                ==
                target_entity_id
            ):

                return prediction

        raise KeyError(
            "Link prediction pair not found."
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top(
        self,
        *,
        metric: LinkPredictionMetric = (
            LinkPredictionMetric
            .ADAMIC_ADAR
        ),
        limit: int = 10,
    ) -> tuple[
        LinkPredictionCandidate,
        ...,
    ]:
        """
        Rank predictions by one metric.
        """

        if not isinstance(
            metric,
            LinkPredictionMetric,
        ):

            raise TypeError(
                "metric must be "
                "LinkPredictionMetric."
            )

        if (
            not isinstance(
                limit,
                int,
            )
            or limit < 0
        ):

            raise ValueError(
                "limit must be a "
                "non-negative integer."
            )

        ordered = sorted(
            self.predictions,
            key=lambda prediction: (
                -prediction.metric_value(
                    metric
                ),
                -prediction.common_neighbors,
                str(
                    prediction
                    .source_entity_id
                ),
                str(
                    prediction
                    .target_entity_id
                ),
            ),
        )

        return tuple(
            ordered[
                :limit
            ]
        )


# ==========================================================
# Service
# ==========================================================


class LinkPredictionService:
    """
    Structural link prediction over normalized graphs.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
        config: (
            LinkPredictionConfig
            | None
        ) = None,
    ) -> LinkPredictionResult:
        """
        Find potential missing graph links.

        No database writes are performed.
        """

        if not isinstance(
            graph,
            NormalizedEntityGraph,
        ):

            raise TypeError(
                "graph must be "
                "NormalizedEntityGraph."
            )

        config = (
            config
            or LinkPredictionConfig()
        )

        if not isinstance(
            config,
            LinkPredictionConfig,
        ):

            raise TypeError(
                "config must be "
                "LinkPredictionConfig."
            )

        existing_edges = (
            self._existing_edge_pairs(
                graph
            )
        )

        candidate_pairs = (
            self._generate_candidate_pairs(
                graph,
                existing_edges=(
                    existing_edges
                ),
            )
        )

        evaluated_candidate_count = len(
            candidate_pairs
        )

        predictions: list[
            LinkPredictionCandidate
        ] = []

        for (
            source_entity_id,
            target_entity_id,
        ) in candidate_pairs:

            prediction = (
                self._score_candidate(
                    graph,
                    source_entity_id=(
                        source_entity_id
                    ),
                    target_entity_id=(
                        target_entity_id
                    ),
                )
            )

            if (
                prediction.common_neighbors
                <
                config.minimum_common_neighbors
            ):

                continue

            predictions.append(
                prediction
            )

        predictions.sort(
            key=lambda prediction: (
                str(
                    prediction
                    .source_entity_id
                ),
                str(
                    prediction
                    .target_entity_id
                ),
            )
        )

        return LinkPredictionResult(
            direction=(
                graph.semantics.direction
            ),
            predictions=tuple(
                predictions
            ),
            node_count=(
                graph.node_count
            ),
            edge_count=(
                graph.edge_count
            ),
            source_edge_count=(
                graph.source_edge_count
            ),
            evaluated_candidate_count=(
                evaluated_candidate_count
            ),
            minimum_common_neighbors=(
                config.minimum_common_neighbors
            ),
        )

    # ==========================================================
    # Existing structural edges
    # ==========================================================

    @staticmethod
    def _existing_edge_pairs(
        graph: NormalizedEntityGraph,
    ) -> set[
        tuple[
            UUID,
            UUID,
        ]
    ]:

        pairs: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for edge in graph.edges:

            if (
                edge.source_id
                ==
                edge.target_id
            ):

                continue

            if (
                graph.semantics.direction
                ==
                GraphDirection.UNDIRECTED
            ):

                first, second = sorted(
                    (
                        edge.source_id,
                        edge.target_id,
                    ),
                    key=str,
                )

                pairs.add(
                    (
                        first,
                        second,
                    )
                )

            else:

                pairs.add(
                    (
                        edge.source_id,
                        edge.target_id,
                    )
                )

        return pairs

    # ==========================================================
    # Candidate generation
    # ==========================================================

    def _generate_candidate_pairs(
        self,
        graph: NormalizedEntityGraph,
        *,
        existing_edges: set[
            tuple[
                UUID,
                UUID,
            ]
        ],
    ) -> tuple[
        tuple[
            UUID,
            UUID,
        ],
        ...,
    ]:
        """
        Generate only two-hop structural candidates.

        This avoids scanning every possible O(N²) pair.

        UNDIRECTED:

            A - X - B
                ↓
            candidate A-B

        DIRECTED:

            A -> X -> B
                 ↓
            candidate A->B
        """

        if (
            graph.semantics.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            candidates = (
                self._generate_undirected_candidates(
                    graph,
                    existing_edges=(
                        existing_edges
                    ),
                )
            )

        else:

            candidates = (
                self._generate_directed_candidates(
                    graph,
                    existing_edges=(
                        existing_edges
                    ),
                )
            )

        return tuple(
            sorted(
                candidates,
                key=lambda pair: (
                    str(
                        pair[
                            0
                        ]
                    ),
                    str(
                        pair[
                            1
                        ]
                    ),
                ),
            )
        )

    # ==========================================================
    # Undirected candidates
    # ==========================================================

    def _generate_undirected_candidates(
        self,
        graph: NormalizedEntityGraph,
        *,
        existing_edges: set[
            tuple[
                UUID,
                UUID,
            ]
        ],
    ) -> set[
        tuple[
            UUID,
            UUID,
        ]
    ]:

        candidates: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for intermediary in sorted(
            graph.nodes,
            key=str,
        ):

            neighbors = tuple(
                neighbor
                for neighbor
                in graph.unique_neighbors(
                    intermediary,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
                if (
                    neighbor
                    !=
                    intermediary
                )
            )

            for (
                first,
                second,
            ) in combinations(
                neighbors,
                2,
            ):

                source, target = sorted(
                    (
                        first,
                        second,
                    ),
                    key=str,
                )

                if source == target:

                    continue

                pair = (
                    source,
                    target,
                )

                if pair in existing_edges:

                    continue

                candidates.add(
                    pair
                )

        return candidates

    # ==========================================================
    # Directed candidates
    # ==========================================================

    def _generate_directed_candidates(
        self,
        graph: NormalizedEntityGraph,
        *,
        existing_edges: set[
            tuple[
                UUID,
                UUID,
            ]
        ],
    ) -> set[
        tuple[
            UUID,
            UUID,
        ]
    ]:
        """
        Directed two-hop prediction:

            source -> intermediary -> target
        """

        candidates: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for intermediary in sorted(
            graph.nodes,
            key=str,
        ):

            predecessors = tuple(
                entity_id
                for entity_id
                in graph.unique_neighbors(
                    intermediary,
                    mode=(
                        GraphNeighborMode
                        .INCOMING
                    ),
                )
                if (
                    entity_id
                    !=
                    intermediary
                )
            )

            successors = tuple(
                entity_id
                for entity_id
                in graph.unique_neighbors(
                    intermediary,
                    mode=(
                        GraphNeighborMode
                        .OUTGOING
                    ),
                )
                if (
                    entity_id
                    !=
                    intermediary
                )
            )

            for source in predecessors:

                for target in successors:

                    if source == target:

                        continue

                    pair = (
                        source,
                        target,
                    )

                    if pair in existing_edges:

                        continue

                    candidates.add(
                        pair
                    )

        return candidates

    # ==========================================================
    # Candidate scoring
    # ==========================================================

    def _score_candidate(
        self,
        graph: NormalizedEntityGraph,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> LinkPredictionCandidate:

        (
            source_neighbors,
            target_neighbors,
        ) = self._candidate_neighbor_sets(
            graph,
            source_entity_id=(
                source_entity_id
            ),
            target_entity_id=(
                target_entity_id
            ),
        )

        common_neighbors = (
            source_neighbors
            &
            target_neighbors
        )

        ordered_common = tuple(
            sorted(
                common_neighbors,
                key=str,
            )
        )

        common_neighbor_count = len(
            ordered_common
        )

        union = (
            source_neighbors
            |
            target_neighbors
        )

        if union:

            jaccard = (
                common_neighbor_count
                /
                len(
                    union
                )
            )

        else:

            jaccard = 0.0

        adamic_adar = (
            self._adamic_adar(
                graph,
                common_neighbors=(
                    ordered_common
                ),
            )
        )

        return LinkPredictionCandidate(
            source_entity_id=(
                source_entity_id
            ),
            target_entity_id=(
                target_entity_id
            ),
            common_neighbor_ids=(
                ordered_common
            ),
            common_neighbors=(
                common_neighbor_count
            ),
            jaccard=jaccard,
            adamic_adar=(
                adamic_adar
            ),
        )

    # ==========================================================
    # Candidate neighborhood semantics
    # ==========================================================

    @staticmethod
    def _candidate_neighbor_sets(
        graph: NormalizedEntityGraph,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> tuple[
        set[
            UUID
        ],
        set[
            UUID
        ],
    ]:
        """
        Neighborhood interpretation.

        UNDIRECTED:

            N(source) ∩ N(target)

        DIRECTED:

            OUT(source) ∩ IN(target)

        Therefore a directed common neighbor represents
        an explicit two-hop path:

            source -> common -> target
        """

        if (
            graph.semantics.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            source_neighbors = set(
                graph.unique_neighbors(
                    source_entity_id,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
            )

            target_neighbors = set(
                graph.unique_neighbors(
                    target_entity_id,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
            )

        else:

            source_neighbors = set(
                graph.unique_neighbors(
                    source_entity_id,
                    mode=(
                        GraphNeighborMode
                        .OUTGOING
                    ),
                )
            )

            target_neighbors = set(
                graph.unique_neighbors(
                    target_entity_id,
                    mode=(
                        GraphNeighborMode
                        .INCOMING
                    ),
                )
            )

        # Endpoints cannot be their own structural
        # intermediary.
        source_neighbors.discard(
            source_entity_id
        )

        source_neighbors.discard(
            target_entity_id
        )

        target_neighbors.discard(
            source_entity_id
        )

        target_neighbors.discard(
            target_entity_id
        )

        return (
            source_neighbors,
            target_neighbors,
        )

    # ==========================================================
    # Adamic-Adar
    # ==========================================================

    @staticmethod
    def _adamic_adar(
        graph: NormalizedEntityGraph,
        *,
        common_neighbors: tuple[
            UUID,
            ...,
        ],
    ) -> float:
        """
        Adamic-Adar:

            sum(
                1 / log(degree(common_neighbor))
            )

        A low-degree intermediary contributes more than
        a high-degree hub.

        Degree uses UNIQUE ALL-neighbor structural
        degree, preventing parallel-edge inflation.
        """

        score = 0.0

        for common_neighbor in (
            common_neighbors
        ):

            neighbors = {
                entity_id
                for entity_id
                in graph.unique_neighbors(
                    common_neighbor,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
                if (
                    entity_id
                    !=
                    common_neighbor
                )
            }

            degree = len(
                neighbors
            )

            # log(1) == 0.
            #
            # A valid two-hop intermediary should
            # normally have degree >= 2 anyway.
            if degree <= 1:

                continue

            score += (
                1.0
                /
                log(
                    degree
                )
            )

        return score