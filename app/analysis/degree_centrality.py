"""
Degree centrality analysis.

Calculates degree-based graph importance metrics from
the normalized analytical graph.

Responsibilities:

- calculate raw degree
- calculate unique-neighbor degree
- calculate incoming degree
- calculate outgoing degree
- calculate normalized degree
- calculate weighted degree / graph strength
- preserve multigraph edge multiplicity
- keep normalized centrality bounded in [0, 1]
- support directed and undirected graphs
- provide deterministic ranking

Does NOT:

- query the database
- modify graph objects
- calculate PageRank
- calculate betweenness
- detect communities
- perform link prediction
"""

from __future__ import annotations

from dataclasses import dataclass

from math import isfinite

from uuid import UUID

from app.analysis.graph_contracts import (
    GraphDirection,
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
class DegreeCentralityNodeResult:
    """
    Degree metrics for one Entity.

    degree:
        Raw edge-incidence degree.

        Parallel edges count separately.

        Undirected self-loop contributes 2.

    unique_degree:
        Number of distinct OTHER Entities connected
        to this Entity.

        Self-loops do not increase unique_degree.

    normalized_degree:
        unique_degree / (N - 1)

        Therefore normalized degree remains inside
        [0, 1] even in multigraphs.

    weighted_degree:
        Sum of analytical edge weights.

        This is also commonly called graph strength.
    """

    entity_id: UUID

    degree: int

    unique_degree: int

    in_degree: int

    out_degree: int

    unique_in_degree: int

    unique_out_degree: int

    normalized_degree: float

    normalized_in_degree: float

    normalized_out_degree: float

    weighted_degree: float

    weighted_in_degree: float

    weighted_out_degree: float

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

        integer_fields = (
            "degree",
            "unique_degree",
            "in_degree",
            "out_degree",
            "unique_in_degree",
            "unique_out_degree",
        )

        for field_name in integer_fields:

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

        normalized_fields = (
            "normalized_degree",
            "normalized_in_degree",
            "normalized_out_degree",
        )

        for field_name in normalized_fields:

            value = float(
                getattr(
                    self,
                    field_name,
                )
            )

            if (
                not isfinite(
                    value
                )
                or not (
                    0.0
                    <= value
                    <= 1.0
                )
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "between 0.0 and 1.0."
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        weighted_fields = (
            "weighted_degree",
            "weighted_in_degree",
            "weighted_out_degree",
        )

        for field_name in weighted_fields:

            value = float(
                getattr(
                    self,
                    field_name,
                )
            )

            if (
                not isfinite(
                    value
                )
                or value < 0.0
            ):

                raise ValueError(
                    f"{field_name} must be finite "
                    "and non-negative."
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def is_isolated(
        self,
    ) -> bool:

        return (
            self.degree
            ==
            0
        )

    @property
    def strength(
        self,
    ) -> float:
        """
        Alias for weighted degree.
        """

        return (
            self.weighted_degree
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DegreeCentralityResult:
    """
    Complete degree-centrality analysis.
    """

    direction: GraphDirection

    scores: tuple[
        DegreeCentralityNodeResult,
        ...,
    ]

    node_count: int

    edge_count: int

    source_edge_count: int

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
                DegreeCentralityNodeResult,
            ):

                raise TypeError(
                    "scores must contain "
                    "DegreeCentralityNodeResult."
                )

            if score.entity_id in seen:

                raise ValueError(
                    "Duplicate entity result."
                )

            seen.add(
                score.entity_id
            )

        if (
            not isinstance(
                self.node_count,
                int,
            )
            or self.node_count < 0
        ):

            raise ValueError(
                "node_count must be "
                "non-negative."
            )

        if (
            not isinstance(
                self.edge_count,
                int,
            )
            or self.edge_count < 0
        ):

            raise ValueError(
                "edge_count must be "
                "non-negative."
            )

        if (
            not isinstance(
                self.source_edge_count,
                int,
            )
            or self.source_edge_count < 0
        ):

            raise ValueError(
                "source_edge_count must be "
                "non-negative."
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

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        entity_id: UUID,
    ) -> DegreeCentralityNodeResult:
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
        DegreeCentralityNodeResult,
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
        metric: str = (
            "normalized_degree"
        ),
        limit: int = 10,
    ) -> tuple[
        DegreeCentralityNodeResult,
        ...,
    ]:
        """
        Rank Entities by one degree metric.

        Deterministic UUID ordering resolves ties.
        """

        allowed_metrics = {
            "degree",
            "unique_degree",
            "in_degree",
            "out_degree",
            "unique_in_degree",
            "unique_out_degree",
            "normalized_degree",
            "normalized_in_degree",
            "normalized_out_degree",
            "weighted_degree",
            "weighted_in_degree",
            "weighted_out_degree",
        }

        if metric not in allowed_metrics:

            raise ValueError(
                "Unsupported degree metric: "
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


class DegreeCentralityService:
    """
    Calculate degree-based metrics from
    NormalizedEntityGraph.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
    ) -> DegreeCentralityResult:
        """
        Analyze the complete graph.

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

        if (
            graph.semantics.direction
            ==
            GraphDirection.DIRECTED
        ):

            scores = (
                self._analyze_directed(
                    graph
                )
            )

        else:

            scores = (
                self._analyze_undirected(
                    graph
                )
            )

        return (
            DegreeCentralityResult(
                direction=(
                    graph.semantics.direction
                ),
                scores=tuple(
                    scores
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
            )
        )

    # ==========================================================
    # Undirected
    # ==========================================================

    def _analyze_undirected(
        self,
        graph: NormalizedEntityGraph,
    ) -> list[
        DegreeCentralityNodeResult
    ]:

        degree = {
            entity_id: 0
            for entity_id
            in graph.nodes
        }

        weighted = {
            entity_id: 0.0
            for entity_id
            in graph.nodes
        }

        neighbors: dict[
            UUID,
            set[
                UUID
            ],
        ] = {
            entity_id: set()
            for entity_id
            in graph.nodes
        }

        for edge in graph.edges:

            source_id = (
                edge.source_id
            )

            target_id = (
                edge.target_id
            )

            # ==================================================
            # Undirected self-loop
            #
            # Standard graph degree convention:
            # one self-loop contributes TWO incidences.
            #
            # It does NOT increase distinct-other-neighbor
            # centrality.
            # ==================================================

            if (
                source_id
                ==
                target_id
            ):

                degree[
                    source_id
                ] += 2

                weighted[
                    source_id
                ] += (
                    2.0
                    *
                    edge.weight
                )

                continue

            degree[
                source_id
            ] += 1

            degree[
                target_id
            ] += 1

            weighted[
                source_id
            ] += edge.weight

            weighted[
                target_id
            ] += edge.weight

            neighbors[
                source_id
            ].add(
                target_id
            )

            neighbors[
                target_id
            ].add(
                source_id
            )

        denominator = (
            self._normalization_denominator(
                graph.node_count
            )
        )

        results: list[
            DegreeCentralityNodeResult
        ] = []

        for entity_id in sorted(
            graph.nodes,
            key=str,
        ):

            unique_degree = len(
                neighbors[
                    entity_id
                ]
            )

            normalized = (
                unique_degree
                /
                denominator
                if denominator > 0
                else 0.0
            )

            raw_degree = (
                degree[
                    entity_id
                ]
            )

            weighted_degree = (
                weighted[
                    entity_id
                ]
            )

            # In an undirected graph incoming and
            # outgoing concepts resolve to the same
            # undirected degree for API consistency.
            results.append(
                DegreeCentralityNodeResult(
                    entity_id=entity_id,
                    degree=raw_degree,
                    unique_degree=(
                        unique_degree
                    ),
                    in_degree=raw_degree,
                    out_degree=raw_degree,
                    unique_in_degree=(
                        unique_degree
                    ),
                    unique_out_degree=(
                        unique_degree
                    ),
                    normalized_degree=(
                        normalized
                    ),
                    normalized_in_degree=(
                        normalized
                    ),
                    normalized_out_degree=(
                        normalized
                    ),
                    weighted_degree=(
                        weighted_degree
                    ),
                    weighted_in_degree=(
                        weighted_degree
                    ),
                    weighted_out_degree=(
                        weighted_degree
                    ),
                )
            )

        return results

    # ==========================================================
    # Directed
    # ==========================================================

    def _analyze_directed(
        self,
        graph: NormalizedEntityGraph,
    ) -> list[
        DegreeCentralityNodeResult
    ]:

        in_degree = {
            entity_id: 0
            for entity_id
            in graph.nodes
        }

        out_degree = {
            entity_id: 0
            for entity_id
            in graph.nodes
        }

        weighted_in = {
            entity_id: 0.0
            for entity_id
            in graph.nodes
        }

        weighted_out = {
            entity_id: 0.0
            for entity_id
            in graph.nodes
        }

        incoming_neighbors: dict[
            UUID,
            set[
                UUID
            ],
        ] = {
            entity_id: set()
            for entity_id
            in graph.nodes
        }

        outgoing_neighbors: dict[
            UUID,
            set[
                UUID
            ],
        ] = {
            entity_id: set()
            for entity_id
            in graph.nodes
        }

        all_neighbors: dict[
            UUID,
            set[
                UUID
            ],
        ] = {
            entity_id: set()
            for entity_id
            in graph.nodes
        }

        for edge in graph.edges:

            source_id = (
                edge.source_id
            )

            target_id = (
                edge.target_id
            )

            out_degree[
                source_id
            ] += 1

            in_degree[
                target_id
            ] += 1

            weighted_out[
                source_id
            ] += edge.weight

            weighted_in[
                target_id
            ] += edge.weight

            # A self-loop contributes one incoming
            # and one outgoing incidence, but does not
            # make the Entity its own distinct-other
            # neighbor.
            if (
                source_id
                ==
                target_id
            ):

                continue

            outgoing_neighbors[
                source_id
            ].add(
                target_id
            )

            incoming_neighbors[
                target_id
            ].add(
                source_id
            )

            all_neighbors[
                source_id
            ].add(
                target_id
            )

            all_neighbors[
                target_id
            ].add(
                source_id
            )

        denominator = (
            self._normalization_denominator(
                graph.node_count
            )
        )

        results: list[
            DegreeCentralityNodeResult
        ] = []

        for entity_id in sorted(
            graph.nodes,
            key=str,
        ):

            raw_in = (
                in_degree[
                    entity_id
                ]
            )

            raw_out = (
                out_degree[
                    entity_id
                ]
            )

            raw_total = (
                raw_in
                +
                raw_out
            )

            unique_in = len(
                incoming_neighbors[
                    entity_id
                ]
            )

            unique_out = len(
                outgoing_neighbors[
                    entity_id
                ]
            )

            unique_total = len(
                all_neighbors[
                    entity_id
                ]
            )

            normalized_in = (
                unique_in
                /
                denominator
                if denominator > 0
                else 0.0
            )

            normalized_out = (
                unique_out
                /
                denominator
                if denominator > 0
                else 0.0
            )

            normalized_total = (
                unique_total
                /
                denominator
                if denominator > 0
                else 0.0
            )

            weight_in = (
                weighted_in[
                    entity_id
                ]
            )

            weight_out = (
                weighted_out[
                    entity_id
                ]
            )

            results.append(
                DegreeCentralityNodeResult(
                    entity_id=entity_id,
                    degree=raw_total,
                    unique_degree=(
                        unique_total
                    ),
                    in_degree=raw_in,
                    out_degree=raw_out,
                    unique_in_degree=(
                        unique_in
                    ),
                    unique_out_degree=(
                        unique_out
                    ),
                    normalized_degree=(
                        normalized_total
                    ),
                    normalized_in_degree=(
                        normalized_in
                    ),
                    normalized_out_degree=(
                        normalized_out
                    ),
                    weighted_degree=(
                        weight_in
                        +
                        weight_out
                    ),
                    weighted_in_degree=(
                        weight_in
                    ),
                    weighted_out_degree=(
                        weight_out
                    ),
                )
            )

        return results

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalization_denominator(
        node_count: int,
    ) -> int:
        """
        Maximum number of distinct OTHER neighbors.

        This is deliberately independent of parallel
        edge multiplicity.
        """

        if node_count <= 1:

            return 0

        return (
            node_count
            -
            1
        )