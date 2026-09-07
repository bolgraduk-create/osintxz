"""
Graph normalization and adjacency layer.

Converts the legacy EntityGraph representation into a
deterministic mathematical graph projection.

Responsibilities:

- validate graph nodes and edges
- apply GraphSemantics
- filter low-confidence edges
- handle self-loops
- preserve or collapse parallel edges
- build outgoing adjacency
- build incoming adjacency
- build all-neighbor adjacency
- preserve multigraph edge multiplicity
- expose unique-neighbor views
- calculate safe simple-graph density
- provide normalization diagnostics

Does NOT:

- query the database
- modify EntityGraph
- modify Relationship objects
- calculate centrality
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
    GraphEdgeObservation,
    GraphNeighborMode,
    GraphParallelEdgePolicy,
    GraphSelfLoopPolicy,
    GraphSemantics,
)

from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
)


# ==========================================================
# Normalized edge
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class NormalizedGraphEdge:
    """
    One analytical graph edge.

    A normalized edge may represent one original
    Relationship or several collapsed Relationships.

    source_edge_count:
        Number of source graph edges represented by
        this analytical edge.

    confidences:
        Original relationship confidence values.

    weight:
        Mathematical edge weight after applying
        GraphSemantics.
    """

    source_id: UUID

    target_id: UUID

    relationship_types: tuple[
        str,
        ...,
    ]

    weight: float

    source_edge_count: int

    confidences: tuple[
        float,
        ...,
    ]

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
            self.relationship_types,
            tuple,
        ):

            raise TypeError(
                "relationship_types must "
                "be a tuple."
            )

        normalized_types = tuple(
            sorted(
                {
                    str(
                        relationship_type
                    ).strip()
                    for relationship_type
                    in self.relationship_types
                    if str(
                        relationship_type
                    ).strip()
                }
            )
        )

        if not normalized_types:

            raise ValueError(
                "Normalized edge requires at "
                "least one relationship type."
            )

        object.__setattr__(
            self,
            "relationship_types",
            normalized_types,
        )

        weight = float(
            self.weight
        )

        if (
            not isfinite(
                weight
            )
            or weight < 0.0
        ):

            raise ValueError(
                "weight must be finite and "
                "non-negative."
            )

        object.__setattr__(
            self,
            "weight",
            weight,
        )

        if (
            not isinstance(
                self.source_edge_count,
                int,
            )
            or self.source_edge_count < 1
        ):

            raise ValueError(
                "source_edge_count must be "
                "a positive integer."
            )

        if not isinstance(
            self.confidences,
            tuple,
        ):

            raise TypeError(
                "confidences must be a tuple."
            )

        normalized_confidences: list[
            float
        ] = []

        for confidence in self.confidences:

            value = float(
                confidence
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
                    "Edge confidences must be "
                    "between 0.0 and 1.0."
                )

            normalized_confidences.append(
                value
            )

        if (
            len(
                normalized_confidences
            )
            !=
            self.source_edge_count
        ):

            raise ValueError(
                "confidences count must match "
                "source_edge_count."
            )

        object.__setattr__(
            self,
            "confidences",
            tuple(
                sorted(
                    normalized_confidences
                )
            ),
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

    @property
    def strongest_confidence(
        self,
    ) -> float:

        return max(
            self.confidences,
            default=0.0,
        )

    @property
    def weakest_confidence(
        self,
    ) -> float:

        return min(
            self.confidences,
            default=0.0,
        )

    @property
    def average_confidence(
        self,
    ) -> float:

        if not self.confidences:

            return 0.0

        return (
            sum(
                self.confidences
            )
            /
            len(
                self.confidences
            )
        )


# ==========================================================
# Normalized graph
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class NormalizedEntityGraph:
    """
    Deterministic analytical graph projection.

    Adjacency tuples preserve edge multiplicity.

    Example:

        A --message--> B
        A --email----> B

    produces:

        neighbors(A) == (B, B)

    while:

        unique_neighbors(A) == (B,)

    This allows later algorithms to deliberately choose
    multigraph or simple-graph semantics.
    """

    semantics: GraphSemantics

    nodes: dict[
        UUID,
        GraphNode,
    ]

    edges: tuple[
        NormalizedGraphEdge,
        ...,
    ]

    outgoing_adjacency: dict[
        UUID,
        tuple[
            UUID,
            ...,
        ],
    ]

    incoming_adjacency: dict[
        UUID,
        tuple[
            UUID,
            ...,
        ],
    ]

    all_adjacency: dict[
        UUID,
        tuple[
            UUID,
            ...,
        ],
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.semantics,
            GraphSemantics,
        ):

            raise TypeError(
                "semantics must be "
                "GraphSemantics."
            )

        if not isinstance(
            self.nodes,
            dict,
        ):

            raise TypeError(
                "nodes must be a dictionary."
            )

        normalized_nodes: dict[
            UUID,
            GraphNode,
        ] = {}

        for entity_id, node in sorted(
            self.nodes.items(),
            key=lambda item: str(
                item[
                    0
                ]
            ),
        ):

            if not isinstance(
                entity_id,
                UUID,
            ):

                raise TypeError(
                    "Graph node keys must be UUID."
                )

            if not isinstance(
                node,
                GraphNode,
            ):

                raise TypeError(
                    "nodes must contain GraphNode "
                    "objects."
                )

            if (
                node.entity_id
                !=
                entity_id
            ):

                raise ValueError(
                    "Graph node dictionary key "
                    "does not match GraphNode.entity_id."
                )

            # Copy legacy mutable GraphNode objects.
            normalized_nodes[
                entity_id
            ] = GraphNode(
                entity_id=node.entity_id,
                label=node.label,
                entity_type=node.entity_type,
            )

        object.__setattr__(
            self,
            "nodes",
            normalized_nodes,
        )

        if not isinstance(
            self.edges,
            tuple,
        ):

            raise TypeError(
                "edges must be a tuple."
            )

        for edge in self.edges:

            if not isinstance(
                edge,
                NormalizedGraphEdge,
            ):

                raise TypeError(
                    "edges must contain only "
                    "NormalizedGraphEdge objects."
                )

            if (
                edge.source_id
                not in normalized_nodes
                or
                edge.target_id
                not in normalized_nodes
            ):

                raise ValueError(
                    "Normalized edge references "
                    "an unknown graph node."
                )

        self._validate_adjacency(
            self.outgoing_adjacency,
            field_name=(
                "outgoing_adjacency"
            ),
        )

        self._validate_adjacency(
            self.incoming_adjacency,
            field_name=(
                "incoming_adjacency"
            ),
        )

        self._validate_adjacency(
            self.all_adjacency,
            field_name="all_adjacency",
        )

    # ==========================================================
    # Node access
    # ==========================================================

    def has_node(
        self,
        entity_id: UUID,
    ) -> bool:

        return (
            entity_id
            in
            self.nodes
        )

    # ==========================================================
    # Neighbors
    # ==========================================================

    def neighbors(
        self,
        entity_id: UUID,
        *,
        mode: GraphNeighborMode = (
            GraphNeighborMode.ALL
        ),
        unique: bool = False,
    ) -> tuple[
        UUID,
        ...,
    ]:
        """
        Return graph neighbors.

        unique=False:
            preserve analytical edge multiplicity.

        unique=True:
            one occurrence per neighboring Entity.
        """

        self._validate_entity_id(
            entity_id
        )

        if not isinstance(
            mode,
            GraphNeighborMode,
        ):

            raise TypeError(
                "mode must be "
                "GraphNeighborMode."
            )

        if (
            self.semantics.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            values = (
                self.all_adjacency[
                    entity_id
                ]
            )

        elif (
            mode
            ==
            GraphNeighborMode.OUTGOING
        ):

            values = (
                self.outgoing_adjacency[
                    entity_id
                ]
            )

        elif (
            mode
            ==
            GraphNeighborMode.INCOMING
        ):

            values = (
                self.incoming_adjacency[
                    entity_id
                ]
            )

        else:

            values = (
                self.all_adjacency[
                    entity_id
                ]
            )

        if not unique:

            return values

        return tuple(
            sorted(
                set(
                    values
                ),
                key=str,
            )
        )

    def unique_neighbors(
        self,
        entity_id: UUID,
        *,
        mode: GraphNeighborMode = (
            GraphNeighborMode.ALL
        ),
    ) -> tuple[
        UUID,
        ...,
    ]:

        return self.neighbors(
            entity_id,
            mode=mode,
            unique=True,
        )

    # ==========================================================
    # Degree helpers
    # ==========================================================

    def degree(
        self,
        entity_id: UUID,
        *,
        mode: GraphNeighborMode = (
            GraphNeighborMode.ALL
        ),
    ) -> int:
        """
        Edge-incidence degree.

        Parallel edges count separately.
        """

        return len(
            self.neighbors(
                entity_id,
                mode=mode,
                unique=False,
            )
        )

    def unique_degree(
        self,
        entity_id: UUID,
        *,
        mode: GraphNeighborMode = (
            GraphNeighborMode.ALL
        ),
    ) -> int:
        """
        Number of distinct neighboring Entities.
        """

        return len(
            self.neighbors(
                entity_id,
                mode=mode,
                unique=True,
            )
        )

    # ==========================================================
    # Graph counts
    # ==========================================================

    @property
    def node_count(
        self,
    ) -> int:

        return len(
            self.nodes
        )

    @property
    def edge_count(
        self,
    ) -> int:
        """
        Number of normalized analytical edges.
        """

        return len(
            self.edges
        )

    @property
    def source_edge_count(
        self,
    ) -> int:
        """
        Number of accepted source EntityGraph edges
        represented by the normalized graph.
        """

        return sum(
            edge.source_edge_count
            for edge
            in self.edges
        )

    @property
    def simple_edge_count(
        self,
    ) -> int:
        """
        Number of unique non-self structural edges.

        Parallel edges and relationship types are
        ignored for simple graph density.
        """

        pairs: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for edge in self.edges:

            if edge.is_self_loop:

                continue

            if (
                self.semantics.direction
                ==
                GraphDirection.DIRECTED
            ):

                pair = (
                    edge.source_id,
                    edge.target_id,
                )

            else:

                pair = tuple(
                    sorted(
                        (
                            edge.source_id,
                            edge.target_id,
                        ),
                        key=str,
                    )
                )

            pairs.add(
                pair
            )

        return len(
            pairs
        )

    # ==========================================================
    # Density
    # ==========================================================

    @property
    def density(
        self,
    ) -> float:
        """
        Safe simple-graph density.

        Parallel relationships do NOT cause density
        greater than 1.0.

        Self-loops are excluded.

        UNDIRECTED:
            E / (N * (N - 1) / 2)

        DIRECTED:
            E / (N * (N - 1))
        """

        node_count = (
            self.node_count
        )

        if node_count < 2:

            return 0.0

        if (
            self.semantics.direction
            ==
            GraphDirection.DIRECTED
        ):

            maximum_edges = (
                node_count
                *
                (
                    node_count
                    -
                    1
                )
            )

        else:

            maximum_edges = (
                node_count
                *
                (
                    node_count
                    -
                    1
                )
                /
                2
            )

        if maximum_edges <= 0:

            return 0.0

        return min(
            1.0,
            (
                self.simple_edge_count
                /
                maximum_edges
            ),
        )

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_entity_id(
        self,
        entity_id: UUID,
    ) -> None:

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        if (
            entity_id
            not in
            self.nodes
        ):

            raise KeyError(
                "Unknown graph node: "
                f"{entity_id}"
            )

    def _validate_adjacency(
        self,
        adjacency: dict[
            UUID,
            tuple[
                UUID,
                ...,
            ],
        ],
        *,
        field_name: str,
    ) -> None:

        if not isinstance(
            adjacency,
            dict,
        ):

            raise TypeError(
                f"{field_name} must be "
                "a dictionary."
            )

        if (
            set(
                adjacency
            )
            !=
            set(
                self.nodes
            )
        ):

            raise ValueError(
                f"{field_name} must contain "
                "exactly all graph nodes."
            )

        for entity_id, neighbors in (
            adjacency.items()
        ):

            if not isinstance(
                neighbors,
                tuple,
            ):

                raise TypeError(
                    f"{field_name} values "
                    "must be tuples."
                )

            for neighbor in neighbors:

                if (
                    neighbor
                    not in
                    self.nodes
                ):

                    raise ValueError(
                        f"{field_name} contains "
                        "an unknown neighbor."
                    )


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphNormalizationDiagnostics:
    """
    Explainable normalization statistics.
    """

    input_node_count: int

    input_edge_count: int

    accepted_edge_count: int

    filtered_edge_count: int

    self_loop_ignored_count: int

    confidence_filtered_count: int

    normalized_edge_count: int

    collapsed_edge_count: int

    @property
    def compression_ratio(
        self,
    ) -> float:
        """
        Fraction of accepted source edges removed by
        edge collapsing.

        0.0 means no collapse.
        """

        if (
            self.accepted_edge_count
            <= 0
        ):

            return 0.0

        return (
            self.collapsed_edge_count
            /
            self.accepted_edge_count
        )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphNormalizationResult:
    """
    Complete graph-normalization result.
    """

    graph: NormalizedEntityGraph

    diagnostics: (
        GraphNormalizationDiagnostics
    )


# ==========================================================
# Service
# ==========================================================


class GraphNormalizationService:
    """
    Build a deterministic analytical graph from
    the legacy EntityGraph model.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def normalize(
        self,
        graph: EntityGraph,
        semantics: (
            GraphSemantics
            | None
        ) = None,
    ) -> GraphNormalizationResult:
        """
        Normalize one EntityGraph.

        No database writes are performed.
        """

        if not isinstance(
            graph,
            EntityGraph,
        ):

            raise TypeError(
                "graph must be EntityGraph."
            )

        semantics = (
            semantics
            or GraphSemantics()
        )

        if not isinstance(
            semantics,
            GraphSemantics,
        ):

            raise TypeError(
                "semantics must be "
                "GraphSemantics."
            )

        nodes = self._copy_nodes(
            graph
        )

        (
            observations,
            self_loop_ignored_count,
            confidence_filtered_count,
        ) = self._prepare_observations(
            graph,
            nodes=nodes,
            semantics=semantics,
        )

        normalized_edges = (
            self._normalize_edges(
                observations,
                semantics=semantics,
            )
        )

        (
            outgoing,
            incoming,
            all_neighbors,
        ) = self._build_adjacency(
            nodes=nodes,
            edges=normalized_edges,
            semantics=semantics,
        )

        normalized_graph = (
            NormalizedEntityGraph(
                semantics=semantics,
                nodes=nodes,
                edges=normalized_edges,
                outgoing_adjacency=(
                    outgoing
                ),
                incoming_adjacency=(
                    incoming
                ),
                all_adjacency=(
                    all_neighbors
                ),
            )
        )

        accepted_edge_count = len(
            observations
        )

        normalized_edge_count = len(
            normalized_edges
        )

        diagnostics = (
            GraphNormalizationDiagnostics(
                input_node_count=len(
                    graph.nodes
                ),
                input_edge_count=len(
                    graph.edges
                ),
                accepted_edge_count=(
                    accepted_edge_count
                ),
                filtered_edge_count=(
                    len(
                        graph.edges
                    )
                    -
                    accepted_edge_count
                ),
                self_loop_ignored_count=(
                    self_loop_ignored_count
                ),
                confidence_filtered_count=(
                    confidence_filtered_count
                ),
                normalized_edge_count=(
                    normalized_edge_count
                ),
                collapsed_edge_count=max(
                    0,
                    (
                        accepted_edge_count
                        -
                        normalized_edge_count
                    ),
                ),
            )
        )

        return GraphNormalizationResult(
            graph=normalized_graph,
            diagnostics=diagnostics,
        )

    # ==========================================================
    # Nodes
    # ==========================================================

    @staticmethod
    def _copy_nodes(
        graph: EntityGraph,
    ) -> dict[
        UUID,
        GraphNode,
    ]:

        nodes: dict[
            UUID,
            GraphNode,
        ] = {}

        for entity_id, node in sorted(
            graph.nodes.items(),
            key=lambda item: str(
                item[
                    0
                ]
            ),
        ):

            if not isinstance(
                entity_id,
                UUID,
            ):

                raise TypeError(
                    "EntityGraph node keys "
                    "must be UUID."
                )

            if not isinstance(
                node,
                GraphNode,
            ):

                raise TypeError(
                    "EntityGraph nodes must "
                    "contain GraphNode objects."
                )

            if (
                node.entity_id
                !=
                entity_id
            ):

                raise ValueError(
                    "EntityGraph node key "
                    "does not match entity_id."
                )

            nodes[
                entity_id
            ] = GraphNode(
                entity_id=node.entity_id,
                label=node.label,
                entity_type=node.entity_type,
            )

        return nodes

    # ==========================================================
    # Raw observations
    # ==========================================================

    def _prepare_observations(
        self,
        graph: EntityGraph,
        *,
        nodes: dict[
            UUID,
            GraphNode,
        ],
        semantics: GraphSemantics,
    ) -> tuple[
        list[
            GraphEdgeObservation
        ],
        int,
        int,
    ]:

        observations: list[
            GraphEdgeObservation
        ] = []

        self_loop_ignored_count = 0

        confidence_filtered_count = 0

        for edge in graph.edges:

            source_id = getattr(
                edge,
                "source_id",
                None,
            )

            target_id = getattr(
                edge,
                "target_id",
                None,
            )

            if (
                source_id
                not in nodes
                or
                target_id
                not in nodes
            ):

                raise ValueError(
                    "EntityGraph edge references "
                    "an unknown node."
                )

            observation = (
                GraphEdgeObservation(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=str(
                        getattr(
                            edge,
                            "relationship_type",
                            "",
                        )
                    ),
                    confidence=float(
                        getattr(
                            edge,
                            "confidence",
                            1.0,
                        )
                    ),
                )
            )

            # Explicit diagnostic accounting before
            # general semantics filtering.
            if observation.is_self_loop:

                if (
                    semantics.self_loop_policy
                    ==
                    GraphSelfLoopPolicy
                    .IGNORE
                ):

                    self_loop_ignored_count += 1

                    continue

            if (
                observation.confidence
                <
                semantics
                .minimum_edge_confidence
            ):

                confidence_filtered_count += 1

                continue

            # REJECT self-loops are raised here.
            if not semantics.accepts_edge(
                observation
            ):

                continue

            observations.append(
                observation
            )

        observations.sort(
            key=self._observation_sort_key
        )

        return (
            observations,
            self_loop_ignored_count,
            confidence_filtered_count,
        )

    # ==========================================================
    # Edge normalization
    # ==========================================================

    def _normalize_edges(
        self,
        observations: list[
            GraphEdgeObservation
        ],
        *,
        semantics: GraphSemantics,
    ) -> tuple[
        NormalizedGraphEdge,
        ...,
    ]:

        if (
            semantics.parallel_edge_policy
            ==
            GraphParallelEdgePolicy
            .KEEP_PARALLEL
        ):

            edges = [
                self._single_edge(
                    observation,
                    semantics=semantics,
                )
                for observation
                in observations
            ]

        else:

            groups: dict[
                tuple[
                    str,
                    ...,
                ],
                list[
                    GraphEdgeObservation
                ],
            ] = {}

            for observation in observations:

                key = semantics.collapse_key(
                    observation
                )

                if key is None:

                    raise RuntimeError(
                        "Collapse policy produced "
                        "no grouping key."
                    )

                groups.setdefault(
                    key,
                    [],
                ).append(
                    observation
                )

            edges = []

            for key in sorted(
                groups
            ):

                edges.append(
                    self._collapsed_edge(
                        groups[
                            key
                        ],
                        semantics=semantics,
                    )
                )

        edges.sort(
            key=self._normalized_edge_sort_key
        )

        return tuple(
            edges
        )

    # ==========================================================
    # Single edge
    # ==========================================================

    def _single_edge(
        self,
        observation: GraphEdgeObservation,
        *,
        semantics: GraphSemantics,
    ) -> NormalizedGraphEdge:

        source_id, target_id = (
            self._project_pair(
                observation,
                semantics=semantics,
            )
        )

        return NormalizedGraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship_types=(
                observation
                .relationship_type,
            ),
            weight=semantics.edge_weight(
                observation
            ),
            source_edge_count=1,
            confidences=(
                observation.confidence,
            ),
        )

    # ==========================================================
    # Collapsed edge
    # ==========================================================

    def _collapsed_edge(
        self,
        observations: list[
            GraphEdgeObservation
        ],
        *,
        semantics: GraphSemantics,
    ) -> NormalizedGraphEdge:

        if not observations:

            raise ValueError(
                "Cannot collapse empty "
                "edge group."
            )

        ordered = sorted(
            observations,
            key=self._observation_sort_key,
        )

        source_id, target_id = (
            self._project_pair(
                ordered[
                    0
                ],
                semantics=semantics,
            )
        )

        weights = [
            semantics.edge_weight(
                observation
            )
            for observation
            in ordered
        ]

        relationship_types = tuple(
            sorted(
                {
                    observation
                    .relationship_type
                    for observation
                    in ordered
                }
            )
        )

        confidences = tuple(
            sorted(
                observation.confidence
                for observation
                in ordered
            )
        )

        return NormalizedGraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship_types=(
                relationship_types
            ),
            weight=(
                semantics.aggregate_weights(
                    weights
                )
            ),
            source_edge_count=len(
                ordered
            ),
            confidences=confidences,
        )

    # ==========================================================
    # Analytical pair projection
    # ==========================================================

    @staticmethod
    def _project_pair(
        observation: GraphEdgeObservation,
        *,
        semantics: GraphSemantics,
    ) -> tuple[
        UUID,
        UUID,
    ]:

        return semantics.canonical_pair(
            observation.source_id,
            observation.target_id,
        )

    # ==========================================================
    # Adjacency
    # ==========================================================

    def _build_adjacency(
        self,
        *,
        nodes: dict[
            UUID,
            GraphNode,
        ],
        edges: tuple[
            NormalizedGraphEdge,
            ...,
        ],
        semantics: GraphSemantics,
    ) -> tuple[
        dict[
            UUID,
            tuple[
                UUID,
                ...,
            ],
        ],
        dict[
            UUID,
            tuple[
                UUID,
                ...,
            ],
        ],
        dict[
            UUID,
            tuple[
                UUID,
                ...,
            ],
        ],
    ]:

        outgoing_lists = {
            entity_id: []
            for entity_id
            in nodes
        }

        incoming_lists = {
            entity_id: []
            for entity_id
            in nodes
        }

        all_lists = {
            entity_id: []
            for entity_id
            in nodes
        }

        for edge in edges:

            source_id = (
                edge.source_id
            )

            target_id = (
                edge.target_id
            )

            # ==================================================
            # Undirected projection
            # ==================================================

            if (
                semantics.direction
                ==
                GraphDirection.UNDIRECTED
            ):

                if (
                    source_id
                    ==
                    target_id
                ):

                    all_lists[
                        source_id
                    ].append(
                        source_id
                    )

                    continue

                all_lists[
                    source_id
                ].append(
                    target_id
                )

                all_lists[
                    target_id
                ].append(
                    source_id
                )

                continue

            # ==================================================
            # Directed projection
            # ==================================================

            outgoing_lists[
                source_id
            ].append(
                target_id
            )

            incoming_lists[
                target_id
            ].append(
                source_id
            )

            if (
                source_id
                ==
                target_id
            ):

                all_lists[
                    source_id
                ].append(
                    source_id
                )

            else:

                all_lists[
                    source_id
                ].append(
                    target_id
                )

                all_lists[
                    target_id
                ].append(
                    source_id
                )

        # For undirected graphs incoming/outgoing are
        # deliberately equivalent to all adjacency.
        if (
            semantics.direction
            ==
            GraphDirection.UNDIRECTED
        ):

            for entity_id in nodes:

                ordered = sorted(
                    all_lists[
                        entity_id
                    ],
                    key=str,
                )

                all_lists[
                    entity_id
                ] = list(
                    ordered
                )

                outgoing_lists[
                    entity_id
                ] = list(
                    ordered
                )

                incoming_lists[
                    entity_id
                ] = list(
                    ordered
                )

        else:

            for entity_id in nodes:

                outgoing_lists[
                    entity_id
                ].sort(
                    key=str
                )

                incoming_lists[
                    entity_id
                ].sort(
                    key=str
                )

                all_lists[
                    entity_id
                ].sort(
                    key=str
                )

        outgoing = {
            entity_id: tuple(
                outgoing_lists[
                    entity_id
                ]
            )
            for entity_id
            in sorted(
                nodes,
                key=str,
            )
        }

        incoming = {
            entity_id: tuple(
                incoming_lists[
                    entity_id
                ]
            )
            for entity_id
            in sorted(
                nodes,
                key=str,
            )
        }

        all_neighbors = {
            entity_id: tuple(
                all_lists[
                    entity_id
                ]
            )
            for entity_id
            in sorted(
                nodes,
                key=str,
            )
        }

        return (
            outgoing,
            incoming,
            all_neighbors,
        )

    # ==========================================================
    # Deterministic ordering
    # ==========================================================

    @staticmethod
    def _observation_sort_key(
        observation: GraphEdgeObservation,
    ) -> tuple[
        str,
        str,
        str,
        float,
    ]:

        return (
            str(
                observation.source_id
            ),
            str(
                observation.target_id
            ),
            observation.relationship_type,
            observation.confidence,
        )

    @staticmethod
    def _normalized_edge_sort_key(
        edge: NormalizedGraphEdge,
    ) -> tuple[
        str,
        str,
        tuple[
            str,
            ...,
        ],
        float,
        int,
        tuple[
            float,
            ...,
        ],
    ]:

        return (
            str(
                edge.source_id
            ),
            str(
                edge.target_id
            ),
            edge.relationship_types,
            edge.weight,
            edge.source_edge_count,
            edge.confidences,
        )