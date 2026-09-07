"""
Graph analysis contracts and semantics.

Defines the common mathematical interpretation of
investigation entity graphs.

Responsibilities:

- define directed / undirected graph semantics
- define incoming / outgoing / all-neighbor traversal
- define parallel-edge handling
- define graph edge weight semantics
- define self-loop handling
- represent validated raw graph edge observations
- provide deterministic canonical edge keys

Does NOT:

- query the database
- mutate Entity or Relationship objects
- normalize a complete graph
- calculate centrality
- calculate PageRank
- detect communities
- perform link prediction
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import isfinite

from uuid import UUID


# ==========================================================
# Direction
# ==========================================================


class GraphDirection(
    str,
    Enum,
):
    """
    Mathematical direction of the analytical graph.
    """

    DIRECTED = "directed"

    UNDIRECTED = "undirected"


# ==========================================================
# Neighbor traversal
# ==========================================================


class GraphNeighborMode(
    str,
    Enum,
):
    """
    Which neighbors should be returned when traversing
    a directed graph.

    For UNDIRECTED graphs all three modes resolve to
    ordinary undirected adjacency.
    """

    OUTGOING = "outgoing"

    INCOMING = "incoming"

    ALL = "all"


# ==========================================================
# Parallel edges
# ==========================================================


class GraphParallelEdgePolicy(
    str,
    Enum,
):
    """
    How multiple Relationship objects between entities
    are represented analytically.

    KEEP_PARALLEL:

        Every Relationship remains a separate edge.

    COLLAPSE_BY_PAIR:

        All relationships between a pair become one
        analytical edge.

    COLLAPSE_BY_PAIR_AND_TYPE:

        Multiple relationships are collapsed only when
        both entity pair and relationship type match.
    """

    KEEP_PARALLEL = "keep_parallel"

    COLLAPSE_BY_PAIR = "collapse_by_pair"

    COLLAPSE_BY_PAIR_AND_TYPE = (
        "collapse_by_pair_and_type"
    )


# ==========================================================
# Weight mode
# ==========================================================


class GraphWeightMode(
    str,
    Enum,
):
    """
    Meaning of analytical edge weight.

    UNWEIGHTED:

        Every accepted edge has weight 1.0.

    CONFIDENCE:

        Relationship.confidence becomes the
        analytical edge weight.
    """

    UNWEIGHTED = "unweighted"

    CONFIDENCE = "confidence"


# ==========================================================
# Collapsed edge weight aggregation
# ==========================================================


class GraphWeightAggregation(
    str,
    Enum,
):
    """
    How weights are combined when parallel edges are
    collapsed.

    MAX is the conservative default because repeated
    correlated relationships must not automatically
    inflate graph strength.
    """

    MAX = "max"

    MEAN = "mean"

    SUM = "sum"


# ==========================================================
# Self-loop handling
# ==========================================================


class GraphSelfLoopPolicy(
    str,
    Enum,
):
    """
    Handling of edges such as:

        Entity A -> Entity A
    """

    IGNORE = "ignore"

    KEEP = "keep"

    REJECT = "reject"


# ==========================================================
# Raw edge observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphEdgeObservation:
    """
    Validated analytical representation of one
    Relationship-like edge.

    This object does not modify or replace the
    SQLAlchemy Relationship model.
    """

    source_id: UUID

    target_id: UUID

    relationship_type: str

    confidence: float = 1.0

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.source_id,
            UUID,
        ):

            raise TypeError(
                "source_id must be UUID."
            )

        if not isinstance(
            self.target_id,
            UUID,
        ):

            raise TypeError(
                "target_id must be UUID."
            )

        if not isinstance(
            self.relationship_type,
            str,
        ):

            raise TypeError(
                "relationship_type must "
                "be a string."
            )

        relationship_type = (
            self.relationship_type.strip()
        )

        if not relationship_type:

            raise ValueError(
                "relationship_type cannot "
                "be empty."
            )

        object.__setattr__(
            self,
            "relationship_type",
            relationship_type,
        )

        confidence = float(
            self.confidence
        )

        if not isfinite(
            confidence
        ):

            raise ValueError(
                "confidence must be finite."
            )

        if not (
            0.0
            <= confidence
            <= 1.0
        ):

            raise ValueError(
                "confidence must be between "
                "0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "confidence",
            confidence,
        )

    @property
    def is_self_loop(
        self,
    ) -> bool:

        return (
            self.source_id
            ==
            self.target_id
        )


# ==========================================================
# Semantics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphSemantics:
    """
    Complete mathematical interpretation of an
    EntityGraph.

    Defaults deliberately preserve the dominant
    behavior of the existing graph analyzers:

        - undirected traversal
        - parallel relationships preserved
        - unweighted BFS / degree semantics

    More advanced algorithms can explicitly request
    directed or confidence-weighted projections.
    """

    direction: GraphDirection = (
        GraphDirection.UNDIRECTED
    )

    parallel_edge_policy: (
        GraphParallelEdgePolicy
    ) = (
        GraphParallelEdgePolicy
        .KEEP_PARALLEL
    )

    weight_mode: GraphWeightMode = (
        GraphWeightMode.UNWEIGHTED
    )

    collapsed_weight_aggregation: (
        GraphWeightAggregation
    ) = (
        GraphWeightAggregation.MAX
    )

    self_loop_policy: (
        GraphSelfLoopPolicy
    ) = (
        GraphSelfLoopPolicy.IGNORE
    )

    minimum_edge_confidence: float = 0.0

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
            self.parallel_edge_policy,
            GraphParallelEdgePolicy,
        ):

            raise TypeError(
                "parallel_edge_policy must be "
                "GraphParallelEdgePolicy."
            )

        if not isinstance(
            self.weight_mode,
            GraphWeightMode,
        ):

            raise TypeError(
                "weight_mode must be "
                "GraphWeightMode."
            )

        if not isinstance(
            self.collapsed_weight_aggregation,
            GraphWeightAggregation,
        ):

            raise TypeError(
                "collapsed_weight_aggregation "
                "must be GraphWeightAggregation."
            )

        if not isinstance(
            self.self_loop_policy,
            GraphSelfLoopPolicy,
        ):

            raise TypeError(
                "self_loop_policy must be "
                "GraphSelfLoopPolicy."
            )

        minimum = float(
            self.minimum_edge_confidence
        )

        if not isfinite(
            minimum
        ):

            raise ValueError(
                "minimum_edge_confidence "
                "must be finite."
            )

        if not (
            0.0
            <= minimum
            <= 1.0
        ):

            raise ValueError(
                "minimum_edge_confidence "
                "must be between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "minimum_edge_confidence",
            minimum,
        )

    # ==========================================================
    # Edge filtering
    # ==========================================================

    def accepts_edge(
        self,
        edge: GraphEdgeObservation,
    ) -> bool:
        """
        Return whether an edge participates in this
        analytical graph projection.
        """

        self._validate_edge(
            edge
        )

        if edge.is_self_loop:

            if (
                self.self_loop_policy
                ==
                GraphSelfLoopPolicy.REJECT
            ):

                raise ValueError(
                    "Self-loop edge rejected by "
                    "graph semantics."
                )

            if (
                self.self_loop_policy
                ==
                GraphSelfLoopPolicy.IGNORE
            ):

                return False

        return (
            edge.confidence
            >=
            self.minimum_edge_confidence
        )

    # ==========================================================
    # Weight
    # ==========================================================

    def edge_weight(
        self,
        edge: GraphEdgeObservation,
    ) -> float:
        """
        Return analytical weight of one accepted edge.
        """

        self._validate_edge(
            edge
        )

        if (
            self.weight_mode
            ==
            GraphWeightMode.UNWEIGHTED
        ):

            return 1.0

        return edge.confidence

    # ==========================================================
    # Canonical pair
    # ==========================================================

    def canonical_pair(
        self,
        source_id: UUID,
        target_id: UUID,
    ) -> tuple[
        UUID,
        UUID,
    ]:
        """
        Return deterministic pair identity.

        DIRECTED:
            source -> target preserved.

        UNDIRECTED:
            pair order canonicalized.
        """

        self._validate_uuid(
            source_id,
            field_name="source_id",
        )

        self._validate_uuid(
            target_id,
            field_name="target_id",
        )

        if (
            self.direction
            ==
            GraphDirection.DIRECTED
        ):

            return (
                source_id,
                target_id,
            )

        return tuple(
            sorted(
                (
                    source_id,
                    target_id,
                ),
                key=str,
            )
        )

    # ==========================================================
    # Parallel-edge grouping
    # ==========================================================

    def collapse_key(
        self,
        edge: GraphEdgeObservation,
    ) -> (
        tuple[
            str,
            ...,
        ]
        | None
    ):
        """
        Return grouping key used by Graph Normalization.

        None means:
            keep this edge independently.
        """

        self._validate_edge(
            edge
        )

        if (
            self.parallel_edge_policy
            ==
            GraphParallelEdgePolicy
            .KEEP_PARALLEL
        ):

            return None

        first, second = (
            self.canonical_pair(
                edge.source_id,
                edge.target_id,
            )
        )

        if (
            self.parallel_edge_policy
            ==
            GraphParallelEdgePolicy
            .COLLAPSE_BY_PAIR
        ):

            return (
                str(
                    first
                ),
                str(
                    second
                ),
            )

        return (
            str(
                first
            ),
            str(
                second
            ),
            edge.relationship_type,
        )

    # ==========================================================
    # Traversal
    # ==========================================================

    def neighbors_from_edge(
        self,
        edge: GraphEdgeObservation,
        entity_id: UUID,
        *,
        mode: GraphNeighborMode = (
            GraphNeighborMode.ALL
        ),
    ) -> tuple[
        UUID,
        ...,
    ]:
        """
        Return neighbors contributed by one edge.

        Result contains zero or one UUID.

        Self-loops are represented once when KEEP is
        enabled.
        """

        self._validate_edge(
            edge
        )

        self._validate_uuid(
            entity_id,
            field_name="entity_id",
        )

        if not isinstance(
            mode,
            GraphNeighborMode,
        ):

            raise TypeError(
                "mode must be "
                "GraphNeighborMode."
            )

        if not self.accepts_edge(
            edge
        ):

            return ()

        # ======================================================
        # Self-loop
        # ======================================================

        if edge.is_self_loop:

            if (
                entity_id
                ==
                edge.source_id
            ):

                return (
                    entity_id,
                )

            return ()

        # ======================================================
        # Undirected projection
        # ======================================================

        if (
            self.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            if (
                entity_id
                ==
                edge.source_id
            ):

                return (
                    edge.target_id,
                )

            if (
                entity_id
                ==
                edge.target_id
            ):

                return (
                    edge.source_id,
                )

            return ()

        # ======================================================
        # Directed projection
        # ======================================================

        if (
            mode
            in {
                GraphNeighborMode.OUTGOING,
                GraphNeighborMode.ALL,
            }
            and
            entity_id
            ==
            edge.source_id
        ):

            return (
                edge.target_id,
            )

        if (
            mode
            in {
                GraphNeighborMode.INCOMING,
                GraphNeighborMode.ALL,
            }
            and
            entity_id
            ==
            edge.target_id
        ):

            return (
                edge.source_id,
            )

        return ()

    # ==========================================================
    # Weight aggregation
    # ==========================================================

    def aggregate_weights(
        self,
        weights: list[
            float
        ],
    ) -> float:
        """
        Aggregate weights for collapsed parallel edges.

        This function does NOT interpret repeated edges
        as independent evidence.
        """

        if not isinstance(
            weights,
            list,
        ):

            raise TypeError(
                "weights must be a list."
            )

        if not weights:

            return 0.0

        normalized: list[
            float
        ] = []

        for weight in weights:

            value = float(
                weight
            )

            if (
                not isfinite(
                    value
                )
                or value < 0.0
            ):

                raise ValueError(
                    "Graph weights must be "
                    "finite and non-negative."
                )

            normalized.append(
                value
            )

        if (
            self.collapsed_weight_aggregation
            ==
            GraphWeightAggregation.MAX
        ):

            return max(
                normalized
            )

        if (
            self.collapsed_weight_aggregation
            ==
            GraphWeightAggregation.MEAN
        ):

            return (
                sum(
                    normalized
                )
                /
                len(
                    normalized
                )
            )

        return sum(
            normalized
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_edge(
        edge: GraphEdgeObservation,
    ) -> None:

        if not isinstance(
            edge,
            GraphEdgeObservation,
        ):

            raise TypeError(
                "edge must be a "
                "GraphEdgeObservation."
            )

    @staticmethod
    def _validate_uuid(
        value: UUID,
        *,
        field_name: str,
    ) -> None:

        if not isinstance(
            value,
            UUID,
        ):

            raise TypeError(
                f"{field_name} must be UUID."
            )