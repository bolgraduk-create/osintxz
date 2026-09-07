"""
Betweenness centrality analysis.

Calculates structural betweenness centrality using
Brandes' algorithm.

Responsibilities:

- calculate exact unweighted betweenness centrality
- account for all shortest paths
- support directed graphs
- support undirected graphs
- avoid parallel-edge path inflation
- ignore self-loops for shortest-path traversal
- support disconnected graphs
- provide raw and normalized scores
- provide deterministic ranking

Does NOT:

- query the database
- modify graph objects
- interpret graph strength as path distance
- calculate weighted shortest paths
- calculate PageRank
- detect communities
- perform link prediction
"""

from __future__ import annotations

from collections import deque

from dataclasses import dataclass

from math import isfinite

from uuid import UUID

from app.analysis.graph_contracts import (
    GraphDirection,
    GraphNeighborMode,
)

from app.analysis.graph_normalization import (
    NormalizedEntityGraph,
)


# ==========================================================
# Node result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class BetweennessCentralityNodeResult:
    """
    Betweenness metrics for one Entity.

    raw_score:
        Number of shortest-path fractions passing
        through the Entity.

        For undirected graphs unordered pairs are
        counted once.

    normalized_score:
        raw_score scaled into [0, 1].

        UNDIRECTED:
            raw * 2 / ((N - 1) * (N - 2))

        DIRECTED:
            raw / ((N - 1) * (N - 2))
    """

    entity_id: UUID

    raw_score: float

    normalized_score: float

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        raw_score = float(
            self.raw_score
        )

        if (
            not isfinite(
                raw_score
            )
            or raw_score < 0.0
        ):

            raise ValueError(
                "raw_score must be finite "
                "and non-negative."
            )

        object.__setattr__(
            self,
            "raw_score",
            raw_score,
        )

        normalized_score = float(
            self.normalized_score
        )

        if (
            not isfinite(
                normalized_score
            )
            or not (
                0.0
                <= normalized_score
                <= 1.0
            )
        ):

            raise ValueError(
                "normalized_score must be "
                "between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "normalized_score",
            normalized_score,
        )

    @property
    def score(
        self,
    ) -> float:
        """
        Default public score.
        """

        return (
            self.normalized_score
        )

    @property
    def is_bridge_candidate(
        self,
    ) -> bool:
        """
        Simple structural diagnostic.

        Explainable bridge classification itself
        belongs to the later explainability layer.
        """

        return (
            self.raw_score
            >
            0.0
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class BetweennessCentralityResult:
    """
    Complete betweenness-centrality result.
    """

    direction: GraphDirection

    scores: tuple[
        BetweennessCentralityNodeResult,
        ...,
    ]

    node_count: int

    edge_count: int

    source_edge_count: int

    algorithm: str = "brandes_unweighted"

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
            self.scores,
            tuple,
        ):

            raise TypeError(
                "scores must be a tuple."
            )

        seen: set[
            UUID
        ] = set()

        for score in self.scores:

            if not isinstance(
                score,
                BetweennessCentralityNodeResult,
            ):

                raise TypeError(
                    "scores must contain only "
                    "BetweennessCentralityNodeResult."
                )

            if score.entity_id in seen:

                raise ValueError(
                    "Duplicate Entity result."
                )

            seen.add(
                score.entity_id
            )

        for field_name in (
            "node_count",
            "edge_count",
            "source_edge_count",
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
            len(
                self.scores
            )
            !=
            self.node_count
        ):

            raise ValueError(
                "scores count must match "
                "node_count."
            )

        if (
            not isinstance(
                self.algorithm,
                str,
            )
            or not self.algorithm.strip()
        ):

            raise ValueError(
                "algorithm cannot be empty."
            )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        entity_id: UUID,
    ) -> BetweennessCentralityNodeResult:
        """
        Return result for one Entity.
        """

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for score in self.scores:

            if (
                score.entity_id
                ==
                entity_id
            ):

                return score

        raise KeyError(
            f"Unknown graph node: {entity_id}"
        )

    @property
    def by_entity(
        self,
    ) -> dict[
        UUID,
        BetweennessCentralityNodeResult,
    ]:

        return {
            score.entity_id: score
            for score
            in self.scores
        }

    # ==========================================================
    # Ranking
    # ==========================================================

    def top(
        self,
        *,
        metric: str = "normalized_score",
        limit: int = 10,
    ) -> tuple[
        BetweennessCentralityNodeResult,
        ...,
    ]:
        """
        Rank Entities by betweenness.

        UUID resolves equal-score ties deterministically.
        """

        if metric not in {
            "raw_score",
            "normalized_score",
        }:

            raise ValueError(
                "Unsupported betweenness metric: "
                f"{metric}"
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
            self.scores,
            key=lambda score: (
                -float(
                    getattr(
                        score,
                        metric,
                    )
                ),
                str(
                    score.entity_id
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


class BetweennessCentralityService:
    """
    Exact unweighted Brandes betweenness centrality.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
    ) -> BetweennessCentralityResult:
        """
        Calculate betweenness centrality.

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

        node_ids = tuple(
            sorted(
                graph.nodes,
                key=str,
            )
        )

        raw_scores = {
            entity_id: 0.0
            for entity_id
            in node_ids
        }

        # ======================================================
        # Brandes algorithm
        # ======================================================

        for source_id in node_ids:

            self._accumulate_from_source(
                graph=graph,
                source_id=source_id,
                raw_scores=raw_scores,
                node_ids=node_ids,
            )

        # ======================================================
        # Undirected correction
        #
        # Every unordered pair was traversed from both
        # directions, so divide by two.
        # ======================================================

        if (
            graph.semantics.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            for entity_id in node_ids:

                raw_scores[
                    entity_id
                ] *= 0.5

        scores = tuple(
            BetweennessCentralityNodeResult(
                entity_id=entity_id,
                raw_score=(
                    raw_scores[
                        entity_id
                    ]
                ),
                normalized_score=(
                    self._normalize_score(
                        raw_score=(
                            raw_scores[
                                entity_id
                            ]
                        ),
                        node_count=len(
                            node_ids
                        ),
                        direction=(
                            graph
                            .semantics
                            .direction
                        ),
                    )
                ),
            )
            for entity_id
            in node_ids
        )

        return (
            BetweennessCentralityResult(
                direction=(
                    graph.semantics.direction
                ),
                scores=scores,
                node_count=(
                    graph.node_count
                ),
                edge_count=(
                    graph.edge_count
                ),
                source_edge_count=(
                    graph.source_edge_count
                ),
            )
        )

    # ==========================================================
    # Brandes source traversal
    # ==========================================================

    def _accumulate_from_source(
        self,
        *,
        graph: NormalizedEntityGraph,
        source_id: UUID,
        raw_scores: dict[
            UUID,
            float,
        ],
        node_ids: tuple[
            UUID,
            ...,
        ],
    ) -> None:
        """
        Single-source Brandes BFS.

        sigma[v]:
            number of shortest paths from source to v

        predecessors[v]:
            predecessor vertices lying on shortest
            paths from source to v

        dependency[v]:
            dependency accumulated during reverse
            traversal.
        """

        stack: list[
            UUID
        ] = []

        predecessors: dict[
            UUID,
            list[
                UUID
            ],
        ] = {
            entity_id: []
            for entity_id
            in node_ids
        }

        sigma = {
            entity_id: 0.0
            for entity_id
            in node_ids
        }

        sigma[
            source_id
        ] = 1.0

        distance = {
            entity_id: -1
            for entity_id
            in node_ids
        }

        distance[
            source_id
        ] = 0

        queue = deque(
            [
                source_id
            ]
        )

        # ======================================================
        # Shortest-path discovery
        # ======================================================

        while queue:

            current = (
                queue.popleft()
            )

            stack.append(
                current
            )

            for neighbor in (
                self._structural_neighbors(
                    graph,
                    current,
                )
            ):

                # First discovery.
                if (
                    distance[
                        neighbor
                    ]
                    <
                    0
                ):

                    queue.append(
                        neighbor
                    )

                    distance[
                        neighbor
                    ] = (
                        distance[
                            current
                        ]
                        +
                        1
                    )

                # Current -> neighbor lies on a
                # shortest path.
                if (
                    distance[
                        neighbor
                    ]
                    ==
                    distance[
                        current
                    ]
                    +
                    1
                ):

                    sigma[
                        neighbor
                    ] += (
                        sigma[
                            current
                        ]
                    )

                    predecessors[
                        neighbor
                    ].append(
                        current
                    )

        # ======================================================
        # Dependency accumulation
        # ======================================================

        dependency = {
            entity_id: 0.0
            for entity_id
            in node_ids
        }

        while stack:

            node_id = (
                stack.pop()
            )

            sigma_node = (
                sigma[
                    node_id
                ]
            )

            if sigma_node > 0.0:

                coefficient = (
                    1.0
                    +
                    dependency[
                        node_id
                    ]
                )

                for predecessor in sorted(
                    predecessors[
                        node_id
                    ],
                    key=str,
                ):

                    dependency[
                        predecessor
                    ] += (
                        (
                            sigma[
                                predecessor
                            ]
                            /
                            sigma_node
                        )
                        *
                        coefficient
                    )

            if (
                node_id
                !=
                source_id
            ):

                raw_scores[
                    node_id
                ] += (
                    dependency[
                        node_id
                    ]
                )

    # ==========================================================
    # Structural neighbors
    # ==========================================================

    @staticmethod
    def _structural_neighbors(
        graph: NormalizedEntityGraph,
        entity_id: UUID,
    ) -> tuple[
        UUID,
        ...,
    ]:
        """
        Return distinct shortest-path neighbors.

        Parallel relationships intentionally do NOT
        create several identical shortest paths.

        Self-loop traversal is excluded because it can
        never improve an unweighted shortest path.
        """

        if (
            graph.semantics.direction
            ==
            GraphDirection.DIRECTED
        ):

            neighbors = (
                graph.unique_neighbors(
                    entity_id,
                    mode=(
                        GraphNeighborMode.OUTGOING
                    ),
                )
            )

        else:

            neighbors = (
                graph.unique_neighbors(
                    entity_id,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
            )

        return tuple(
            neighbor
            for neighbor
            in neighbors
            if (
                neighbor
                !=
                entity_id
            )
        )

    # ==========================================================
    # Normalization
    # ==========================================================

    @staticmethod
    def _normalize_score(
        *,
        raw_score: float,
        node_count: int,
        direction: GraphDirection,
    ) -> float:
        """
        Normalize structural betweenness into [0, 1].

        Undirected maximum:
            (N - 1)(N - 2) / 2

        Directed maximum:
            (N - 1)(N - 2)
        """

        if node_count <= 2:

            return 0.0

        denominator = (
            (
                node_count
                -
                1
            )
            *
            (
                node_count
                -
                2
            )
        )

        if (
            direction
            ==
            GraphDirection.UNDIRECTED
        ):

            score = (
                2.0
                *
                raw_score
                /
                denominator
            )

        else:

            score = (
                raw_score
                /
                denominator
            )

        # Numerical safety.
        return min(
            1.0,
            max(
                0.0,
                score,
            ),
        )