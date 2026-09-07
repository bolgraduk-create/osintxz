"""
Louvain community detection.

Detects densely connected structural communities
inside normalized investigation graphs.

Responsibilities:

- perform deterministic Louvain community detection
- optimize weighted modularity
- support multilevel graph aggregation
- support unweighted and confidence-weighted graphs
- preserve parallel-edge influence through weight
- explicitly project directed graphs to undirected form
- handle disconnected and isolated Entities
- provide modularity diagnostics
- provide deterministic community ordering

Does NOT:

- query the database
- modify graph objects
- replace connected-components analysis
- calculate centrality
- perform link prediction
- persist communities
"""

from __future__ import annotations

from collections import defaultdict

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
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LouvainConfig:
    """
    Louvain numerical and semantic configuration.

    resolution:

        Standard modularity resolution parameter.

        1.0:
            ordinary Louvain modularity.

        > 1.0:
            favors smaller communities.

        < 1.0:
            favors larger communities.

    project_directed_to_undirected:

        Louvain in this phase uses the standard
        undirected weighted modularity model.

        Directed EntityGraphs therefore require an
        explicit undirected projection.

        The projection never mutates the original
        NormalizedEntityGraph.
    """

    resolution: float = 1.0

    tolerance: float = 1e-12

    max_passes: int = 100

    max_levels: int = 20

    project_directed_to_undirected: bool = True

    def __post_init__(
        self,
    ) -> None:

        resolution = float(
            self.resolution
        )

        if (
            not isfinite(
                resolution
            )
            or resolution <= 0.0
        ):

            raise ValueError(
                "resolution must be finite "
                "and greater than 0.0."
            )

        object.__setattr__(
            self,
            "resolution",
            resolution,
        )

        tolerance = float(
            self.tolerance
        )

        if (
            not isfinite(
                tolerance
            )
            or tolerance <= 0.0
        ):

            raise ValueError(
                "tolerance must be finite "
                "and greater than 0.0."
            )

        object.__setattr__(
            self,
            "tolerance",
            tolerance,
        )

        if (
            not isinstance(
                self.max_passes,
                int,
            )
            or self.max_passes < 1
        ):

            raise ValueError(
                "max_passes must be "
                "a positive integer."
            )

        if (
            not isinstance(
                self.max_levels,
                int,
            )
            or self.max_levels < 1
        ):

            raise ValueError(
                "max_levels must be "
                "a positive integer."
            )

        if not isinstance(
            self.project_directed_to_undirected,
            bool,
        ):

            raise TypeError(
                "project_directed_to_undirected "
                "must be bool."
            )


# ==========================================================
# Community
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LouvainCommunity:
    """
    One detected structural community.
    """

    community_id: int

    entity_ids: tuple[
        UUID,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.community_id,
                int,
            )
            or self.community_id < 0
        ):

            raise ValueError(
                "community_id must be "
                "a non-negative integer."
            )

        if not isinstance(
            self.entity_ids,
            tuple,
        ):

            raise TypeError(
                "entity_ids must be a tuple."
            )

        normalized: list[
            UUID
        ] = []

        seen: set[
            UUID
        ] = set()

        for entity_id in self.entity_ids:

            if not isinstance(
                entity_id,
                UUID,
            ):

                raise TypeError(
                    "Community Entity IDs "
                    "must be UUID."
                )

            if entity_id in seen:

                raise ValueError(
                    "Community contains duplicate "
                    "Entity IDs."
                )

            seen.add(
                entity_id
            )

            normalized.append(
                entity_id
            )

        if not normalized:

            raise ValueError(
                "Community cannot be empty."
            )

        object.__setattr__(
            self,
            "entity_ids",
            tuple(
                sorted(
                    normalized,
                    key=str,
                )
            ),
        )

    @property
    def size(
        self,
    ) -> int:

        return len(
            self.entity_ids
        )

    @property
    def is_singleton(
        self,
    ) -> bool:

        return (
            self.size
            ==
            1
        )

    def contains(
        self,
        entity_id: UUID,
    ) -> bool:

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        return (
            entity_id
            in
            self.entity_ids
        )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LouvainResult:
    """
    Complete Louvain result.
    """

    communities: tuple[
        LouvainCommunity,
        ...,
    ]

    modularity: float

    resolution: float

    levels: int

    passes: int

    source_direction: GraphDirection

    used_undirected_projection: bool

    node_count: int

    edge_count: int

    source_edge_count: int

    algorithm: str = "louvain"

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.communities,
            tuple,
        ):

            raise TypeError(
                "communities must be a tuple."
            )

        seen_entities: set[
            UUID
        ] = set()

        seen_ids: set[
            int
        ] = set()

        for community in self.communities:

            if not isinstance(
                community,
                LouvainCommunity,
            ):

                raise TypeError(
                    "communities must contain "
                    "LouvainCommunity objects."
                )

            if (
                community.community_id
                in seen_ids
            ):

                raise ValueError(
                    "Duplicate community_id."
                )

            seen_ids.add(
                community.community_id
            )

            for entity_id in (
                community.entity_ids
            ):

                if (
                    entity_id
                    in seen_entities
                ):

                    raise ValueError(
                        "Entity appears in multiple "
                        "communities."
                    )

                seen_entities.add(
                    entity_id
                )

        modularity = float(
            self.modularity
        )

        if not isfinite(
            modularity
        ):

            raise ValueError(
                "modularity must be finite."
            )

        object.__setattr__(
            self,
            "modularity",
            modularity,
        )

        resolution = float(
            self.resolution
        )

        if (
            not isfinite(
                resolution
            )
            or resolution <= 0.0
        ):

            raise ValueError(
                "resolution must be finite "
                "and greater than 0.0."
            )

        object.__setattr__(
            self,
            "resolution",
            resolution,
        )

        for field_name in (
            "levels",
            "passes",
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

        if not isinstance(
            self.source_direction,
            GraphDirection,
        ):

            raise TypeError(
                "source_direction must be "
                "GraphDirection."
            )

        if not isinstance(
            self.used_undirected_projection,
            bool,
        ):

            raise TypeError(
                "used_undirected_projection "
                "must be bool."
            )

        if (
            len(
                seen_entities
            )
            !=
            self.node_count
        ):

            raise ValueError(
                "Communities must cover every "
                "graph node exactly once."
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
    # Statistics
    # ==========================================================

    @property
    def community_count(
        self,
    ) -> int:

        return len(
            self.communities
        )

    @property
    def largest_community_size(
        self,
    ) -> int:

        return max(
            (
                community.size
                for community
                in self.communities
            ),
            default=0,
        )

    @property
    def singleton_count(
        self,
    ) -> int:

        return sum(
            1
            for community
            in self.communities
            if community.is_singleton
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_community(
        self,
        entity_id: UUID,
    ) -> LouvainCommunity:
        """
        Return community containing one Entity.
        """

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for community in self.communities:

            if (
                entity_id
                in
                community.entity_ids
            ):

                return community

        raise KeyError(
            f"Unknown graph node: {entity_id}"
        )

    def same_community(
        self,
        first_entity_id: UUID,
        second_entity_id: UUID,
    ) -> bool:
        """
        Determine whether two Entities belong to the
        same Louvain community.
        """

        first = self.get_community(
            first_entity_id
        )

        second = self.get_community(
            second_entity_id
        )

        return (
            first.community_id
            ==
            second.community_id
        )


# ==========================================================
# Internal graph
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class _LouvainGraph:
    """
    Internal weighted undirected graph.

    Nodes are deterministic integer supernode IDs.

    edges contains each undirected edge exactly once.

    Self-loop:
        source == target
    """

    nodes: tuple[
        int,
        ...,
    ]

    edges: tuple[
        tuple[
            int,
            int,
            float,
        ],
        ...,
    ]


# ==========================================================
# Service
# ==========================================================


class LouvainCommunityDetectionService:
    """
    Deterministic multilevel Louvain implementation.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
        config: (
            LouvainConfig
            | None
        ) = None,
    ) -> LouvainResult:
        """
        Detect graph communities.

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
            or LouvainConfig()
        )

        if not isinstance(
            config,
            LouvainConfig,
        ):

            raise TypeError(
                "config must be LouvainConfig."
            )

        source_direction = (
            graph.semantics.direction
        )

        used_projection = (
            source_direction
            ==
            GraphDirection.DIRECTED
        )

        if (
            used_projection
            and
            not config
            .project_directed_to_undirected
        ):

            raise ValueError(
                "Directed graph requires explicit "
                "undirected projection for Louvain."
            )

        original_entity_ids = tuple(
            sorted(
                graph.nodes,
                key=str,
            )
        )

        node_count = len(
            original_entity_ids
        )

        # ======================================================
        # Empty graph
        # ======================================================

        if node_count == 0:

            return LouvainResult(
                communities=(),
                modularity=0.0,
                resolution=(
                    config.resolution
                ),
                levels=0,
                passes=0,
                source_direction=(
                    source_direction
                ),
                used_undirected_projection=(
                    used_projection
                ),
                node_count=0,
                edge_count=(
                    graph.edge_count
                ),
                source_edge_count=(
                    graph.source_edge_count
                ),
            )

        (
            internal_graph,
            memberships,
        ) = self._build_initial_graph(
            graph,
            original_entity_ids=(
                original_entity_ids
            ),
        )

        # Keep the original projected graph for final
        # modularity calculation.
        original_internal_graph = (
            internal_graph
        )

        original_memberships = {
            node_id: set(
                entity_ids
            )
            for (
                node_id,
                entity_ids,
            )
            in memberships.items()
        }

        current_graph = (
            internal_graph
        )

        current_memberships = (
            memberships
        )

        final_memberships = {
            node_id: set(
                entity_ids
            )
            for (
                node_id,
                entity_ids,
            )
            in memberships.items()
        }

        levels = 0

        total_passes = 0

        # ======================================================
        # Multilevel Louvain
        # ======================================================

        for level_index in range(
            config.max_levels
        ):

            (
                partition,
                passes,
            ) = self._local_moving_phase(
                current_graph,
                config=config,
            )

            total_passes += (
                passes
            )

            levels = (
                level_index
                +
                1
            )

            grouped_nodes = (
                self._partition_groups(
                    current_graph.nodes,
                    partition=partition,
                )
            )

            final_memberships = (
                self._combine_memberships(
                    grouped_nodes,
                    current_memberships=(
                        current_memberships
                    ),
                )
            )

            # No merge happened at this level.
            if (
                len(
                    grouped_nodes
                )
                ==
                len(
                    current_graph.nodes
                )
            ):

                break

            (
                current_graph,
                current_memberships,
            ) = self._aggregate_graph(
                current_graph,
                grouped_nodes=(
                    grouped_nodes
                ),
                current_memberships=(
                    current_memberships
                ),
            )

        communities = (
            self._build_result_communities(
                final_memberships
            )
        )

        # Map original UUID -> final community ID.
        final_assignment: dict[
            UUID,
            int,
        ] = {}

        for community in communities:

            for entity_id in (
                community.entity_ids
            ):

                final_assignment[
                    entity_id
                ] = (
                    community
                    .community_id
                )

        modularity = (
            self._calculate_original_modularity(
                original_graph=(
                    original_internal_graph
                ),
                original_memberships=(
                    original_memberships
                ),
                final_assignment=(
                    final_assignment
                ),
                resolution=(
                    config.resolution
                ),
            )
        )

        return LouvainResult(
            communities=communities,
            modularity=modularity,
            resolution=(
                config.resolution
            ),
            levels=levels,
            passes=total_passes,
            source_direction=(
                source_direction
            ),
            used_undirected_projection=(
                used_projection
            ),
            node_count=node_count,
            edge_count=(
                graph.edge_count
            ),
            source_edge_count=(
                graph.source_edge_count
            ),
        )

    # ==========================================================
    # Initial undirected projection
    # ==========================================================

    def _build_initial_graph(
        self,
        graph: NormalizedEntityGraph,
        *,
        original_entity_ids: tuple[
            UUID,
            ...,
        ],
    ) -> tuple[
        _LouvainGraph,
        dict[
            int,
            set[
                UUID
            ],
        ],
    ]:

        entity_to_node = {
            entity_id: index
            for index, entity_id
            in enumerate(
                original_entity_ids
            )
        }

        memberships = {
            index: {
                entity_id
            }
            for index, entity_id
            in enumerate(
                original_entity_ids
            )
        }

        edge_weights: dict[
            tuple[
                int,
                int,
            ],
            float,
        ] = defaultdict(
            float
        )

        for edge in graph.edges:

            weight = float(
                edge.weight
            )

            if (
                not isfinite(
                    weight
                )
                or weight < 0.0
            ):

                raise ValueError(
                    "Louvain edge weights must be "
                    "finite and non-negative."
                )

            # Zero-strength edge does not influence
            # weighted modularity.
            if weight <= 0.0:

                continue

            source = entity_to_node[
                edge.source_id
            ]

            target = entity_to_node[
                edge.target_id
            ]

            first, second = sorted(
                (
                    source,
                    target,
                )
            )

            edge_weights[
                (
                    first,
                    second,
                )
            ] += weight

        edges = tuple(
            (
                source,
                target,
                edge_weights[
                    (
                        source,
                        target,
                    )
                ],
            )
            for (
                source,
                target,
            )
            in sorted(
                edge_weights
            )
        )

        return (
            _LouvainGraph(
                nodes=tuple(
                    range(
                        len(
                            original_entity_ids
                        )
                    )
                ),
                edges=edges,
            ),
            memberships,
        )

    # ==========================================================
    # Local moving
    # ==========================================================

    def _local_moving_phase(
        self,
        graph: _LouvainGraph,
        *,
        config: LouvainConfig,
    ) -> tuple[
        dict[
            int,
            int,
        ],
        int,
    ]:
        """
        Louvain phase 1.

        Start with one community per node and move
        nodes whenever modularity strictly increases.
        """

        (
            adjacency,
            degrees,
            total_weight,
        ) = self._graph_statistics(
            graph
        )

        partition = {
            node_id: node_id
            for node_id
            in graph.nodes
        }

        # No weighted edges:
        # every node remains its own community.
        if total_weight <= 0.0:

            return (
                partition,
                0,
            )

        community_degree = {
            node_id: (
                degrees[
                    node_id
                ]
            )
            for node_id
            in graph.nodes
        }

        next_community_id = (
            max(
                graph.nodes,
                default=-1,
            )
            +
            1
        )

        passes = 0

        for _ in range(
            config.max_passes
        ):

            passes += 1

            moved = False

            for node_id in graph.nodes:

                current_community = (
                    partition[
                        node_id
                    ]
                )

                node_degree = (
                    degrees[
                        node_id
                    ]
                )

                # Isolated weighted node cannot improve
                # modularity by moving.
                if node_degree <= 0.0:

                    continue

                weights_to_community: dict[
                    int,
                    float,
                ] = defaultdict(
                    float
                )

                for (
                    neighbor,
                    weight,
                ) in adjacency[
                    node_id
                ].items():

                    weights_to_community[
                        partition[
                            neighbor
                        ]
                    ] += weight

                current_internal_weight = (
                    weights_to_community.get(
                        current_community,
                        0.0,
                    )
                )

                current_total_degree = (
                    community_degree[
                        current_community
                    ]
                )

                best_community = (
                    current_community
                )

                best_gain = 0.0

                # ==============================================
                # Existing neighboring communities
                # ==============================================

                candidate_communities = sorted(
                    set(
                        weights_to_community
                    )
                    -
                    {
                        current_community
                    }
                )

                for candidate in (
                    candidate_communities
                ):

                    candidate_internal_weight = (
                        weights_to_community[
                            candidate
                        ]
                    )

                    candidate_total_degree = (
                        community_degree[
                            candidate
                        ]
                    )

                    gain = (
                        self._move_gain(
                            node_degree=(
                                node_degree
                            ),
                            current_internal_weight=(
                                current_internal_weight
                            ),
                            candidate_internal_weight=(
                                candidate_internal_weight
                            ),
                            current_total_degree=(
                                current_total_degree
                            ),
                            candidate_total_degree=(
                                candidate_total_degree
                            ),
                            total_weight=(
                                total_weight
                            ),
                            resolution=(
                                config.resolution
                            ),
                        )
                    )

                    if (
                        gain
                        >
                        best_gain
                        +
                        config.tolerance
                    ):

                        best_gain = (
                            gain
                        )

                        best_community = (
                            candidate
                        )

                    elif (
                        abs(
                            gain
                            -
                            best_gain
                        )
                        <=
                        config.tolerance
                        and gain
                        >
                        config.tolerance
                        and candidate
                        <
                        best_community
                    ):

                        best_community = (
                            candidate
                        )

                # ==============================================
                # New singleton community candidate
                #
                # Allows a node to leave an already formed
                # community when doing so improves modularity.
                # ==============================================

                remaining_current_degree = (
                    current_total_degree
                    -
                    node_degree
                )

                if (
                    remaining_current_degree
                    >
                    config.tolerance
                ):

                    singleton_gain = (
                        self._move_gain(
                            node_degree=(
                                node_degree
                            ),
                            current_internal_weight=(
                                current_internal_weight
                            ),
                            candidate_internal_weight=0.0,
                            current_total_degree=(
                                current_total_degree
                            ),
                            candidate_total_degree=0.0,
                            total_weight=(
                                total_weight
                            ),
                            resolution=(
                                config.resolution
                            ),
                        )
                    )

                    if (
                        singleton_gain
                        >
                        best_gain
                        +
                        config.tolerance
                    ):

                        best_community = (
                            next_community_id
                        )

                        best_gain = (
                            singleton_gain
                        )

                # ==============================================
                # Apply move
                # ==============================================

                if (
                    best_community
                    ==
                    current_community
                ):

                    continue

                community_degree[
                    current_community
                ] -= node_degree

                if (
                    abs(
                        community_degree[
                            current_community
                        ]
                    )
                    <=
                    config.tolerance
                ):

                    community_degree[
                        current_community
                    ] = 0.0

                if (
                    best_community
                    ==
                    next_community_id
                ):

                    community_degree[
                        best_community
                    ] = 0.0

                    next_community_id += 1

                community_degree[
                    best_community
                ] = (
                    community_degree.get(
                        best_community,
                        0.0,
                    )
                    +
                    node_degree
                )

                partition[
                    node_id
                ] = (
                    best_community
                )

                moved = True

            if not moved:

                break

        return (
            partition,
            passes,
        )

    # ==========================================================
    # Modularity gain
    # ==========================================================

    @staticmethod
    def _move_gain(
        *,
        node_degree: float,
        current_internal_weight: float,
        candidate_internal_weight: float,
        current_total_degree: float,
        candidate_total_degree: float,
        total_weight: float,
        resolution: float,
    ) -> float:
        """
        Exact modularity difference for moving one node
        from its current community to another community.

        Q = sum_c [
            internal_weight_c / m
            -
            resolution * (degree_sum_c / (2m))^2
        ]

        Self-loop contribution is constant during the
        move and therefore cancels.
        """

        if total_weight <= 0.0:

            return 0.0

        structural_gain = (
            (
                candidate_internal_weight
                -
                current_internal_weight
            )
            /
            total_weight
        )

        null_model_gain = (
            resolution
            *
            node_degree
            *
            (
                candidate_total_degree
                -
                current_total_degree
                +
                node_degree
            )
            /
            (
                2.0
                *
                total_weight
                *
                total_weight
            )
        )

        return (
            structural_gain
            -
            null_model_gain
        )

    # ==========================================================
    # Graph statistics
    # ==========================================================

    @staticmethod
    def _graph_statistics(
        graph: _LouvainGraph,
    ) -> tuple[
        dict[
            int,
            dict[
                int,
                float,
            ],
        ],
        dict[
            int,
            float,
        ],
        float,
    ]:
        """
        Build adjacency and weighted degrees.

        Self-loop contributes twice to weighted degree,
        matching standard undirected graph semantics.
        """

        adjacency: dict[
            int,
            dict[
                int,
                float,
            ],
        ] = {
            node_id: {}
            for node_id
            in graph.nodes
        }

        loops = {
            node_id: 0.0
            for node_id
            in graph.nodes
        }

        total_weight = 0.0

        for (
            source,
            target,
            weight,
        ) in graph.edges:

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
                    "Internal Louvain weight must "
                    "be finite and non-negative."
                )

            if value <= 0.0:

                continue

            total_weight += value

            if source == target:

                loops[
                    source
                ] += value

                continue

            adjacency[
                source
            ][
                target
            ] = (
                adjacency[
                    source
                ].get(
                    target,
                    0.0,
                )
                +
                value
            )

            adjacency[
                target
            ][
                source
            ] = (
                adjacency[
                    target
                ].get(
                    source,
                    0.0,
                )
                +
                value
            )

        degrees = {
            node_id: (
                sum(
                    adjacency[
                        node_id
                    ].values()
                )
                +
                (
                    2.0
                    *
                    loops[
                        node_id
                    ]
                )
            )
            for node_id
            in graph.nodes
        }

        return (
            adjacency,
            degrees,
            total_weight,
        )

    # ==========================================================
    # Partition groups
    # ==========================================================

    @staticmethod
    def _partition_groups(
        nodes: tuple[
            int,
            ...,
        ],
        *,
        partition: dict[
            int,
            int,
        ],
    ) -> tuple[
        tuple[
            int,
            ...,
        ],
        ...,
    ]:

        groups: dict[
            int,
            list[
                int
            ],
        ] = defaultdict(
            list
        )

        for node_id in nodes:

            groups[
                partition[
                    node_id
                ]
            ].append(
                node_id
            )

        ordered = [
            tuple(
                sorted(
                    members
                )
            )
            for members
            in groups.values()
        ]

        ordered.sort()

        return tuple(
            ordered
        )

    # ==========================================================
    # Membership combination
    # ==========================================================

    @staticmethod
    def _combine_memberships(
        grouped_nodes: tuple[
            tuple[
                int,
                ...,
            ],
            ...,
        ],
        *,
        current_memberships: dict[
            int,
            set[
                UUID
            ],
        ],
    ) -> dict[
        int,
        set[
            UUID
        ],
    ]:

        combined_sets: list[
            set[
                UUID
            ]
        ] = []

        for group in grouped_nodes:

            entity_ids: set[
                UUID
            ] = set()

            for node_id in group:

                entity_ids.update(
                    current_memberships[
                        node_id
                    ]
                )

            combined_sets.append(
                entity_ids
            )

        combined_sets.sort(
            key=lambda values: tuple(
                str(
                    entity_id
                )
                for entity_id
                in sorted(
                    values,
                    key=str,
                )
            )
        )

        return {
            index: set(
                values
            )
            for index, values
            in enumerate(
                combined_sets
            )
        }

    # ==========================================================
    # Graph aggregation
    # ==========================================================

    def _aggregate_graph(
        self,
        graph: _LouvainGraph,
        *,
        grouped_nodes: tuple[
            tuple[
                int,
                ...,
            ],
            ...,
        ],
        current_memberships: dict[
            int,
            set[
                UUID
            ],
        ],
    ) -> tuple[
        _LouvainGraph,
        dict[
            int,
            set[
                UUID
            ],
        ],
    ]:

        # Order groups by the original UUID membership
        # represented by each supernode.
        group_data: list[
            tuple[
                tuple[
                    UUID,
                    ...,
                ],
                tuple[
                    int,
                    ...,
                ],
            ]
        ] = []

        for group in grouped_nodes:

            original_entities: set[
                UUID
            ] = set()

            for node_id in group:

                original_entities.update(
                    current_memberships[
                        node_id
                    ]
                )

            ordered_entities = tuple(
                sorted(
                    original_entities,
                    key=str,
                )
            )

            group_data.append(
                (
                    ordered_entities,
                    group,
                )
            )

        group_data.sort(
            key=lambda item: tuple(
                str(
                    entity_id
                )
                for entity_id
                in item[
                    0
                ]
            )
        )

        old_to_new: dict[
            int,
            int,
        ] = {}

        new_memberships: dict[
            int,
            set[
                UUID
            ],
        ] = {}

        for new_id, (
            original_entities,
            group,
        ) in enumerate(
            group_data
        ):

            new_memberships[
                new_id
            ] = set(
                original_entities
            )

            for old_id in group:

                old_to_new[
                    old_id
                ] = (
                    new_id
                )

        edge_weights: dict[
            tuple[
                int,
                int,
            ],
            float,
        ] = defaultdict(
            float
        )

        for (
            source,
            target,
            weight,
        ) in graph.edges:

            new_source = (
                old_to_new[
                    source
                ]
            )

            new_target = (
                old_to_new[
                    target
                ]
            )

            first, second = sorted(
                (
                    new_source,
                    new_target,
                )
            )

            edge_weights[
                (
                    first,
                    second,
                )
            ] += weight

        new_edges = tuple(
            (
                source,
                target,
                edge_weights[
                    (
                        source,
                        target,
                    )
                ],
            )
            for (
                source,
                target,
            )
            in sorted(
                edge_weights
            )
        )

        return (
            _LouvainGraph(
                nodes=tuple(
                    range(
                        len(
                            group_data
                        )
                    )
                ),
                edges=new_edges,
            ),
            new_memberships,
        )

    # ==========================================================
    # Result communities
    # ==========================================================

    @staticmethod
    def _build_result_communities(
        memberships: dict[
            int,
            set[
                UUID
            ],
        ],
    ) -> tuple[
        LouvainCommunity,
        ...,
    ]:

        community_sets = [
            tuple(
                sorted(
                    entity_ids,
                    key=str,
                )
            )
            for entity_ids
            in memberships.values()
        ]

        # Largest communities first.
        #
        # UUID sequence resolves equal-size ties.
        community_sets.sort(
            key=lambda entity_ids: (
                -len(
                    entity_ids
                ),
                tuple(
                    str(
                        entity_id
                    )
                    for entity_id
                    in entity_ids
                ),
            )
        )

        return tuple(
            LouvainCommunity(
                community_id=index,
                entity_ids=entity_ids,
            )
            for index, entity_ids
            in enumerate(
                community_sets
            )
        )

    # ==========================================================
    # Final modularity
    # ==========================================================

    def _calculate_original_modularity(
        self,
        *,
        original_graph: _LouvainGraph,
        original_memberships: dict[
            int,
            set[
                UUID
            ],
        ],
        final_assignment: dict[
            UUID,
            int,
        ],
        resolution: float,
    ) -> float:
        """
        Calculate weighted modularity on the ORIGINAL
        projected graph.

        This avoids using contracted-supernode topology
        when reporting the final score.
        """

        (
            _,
            degrees,
            total_weight,
        ) = self._graph_statistics(
            original_graph
        )

        if total_weight <= 0.0:

            return 0.0

        node_to_community: dict[
            int,
            int,
        ] = {}

        for (
            node_id,
            entity_ids,
        ) in original_memberships.items():

            if len(
                entity_ids
            ) != 1:

                raise ValueError(
                    "Original Louvain membership "
                    "must contain one Entity per node."
                )

            entity_id = next(
                iter(
                    entity_ids
                )
            )

            node_to_community[
                node_id
            ] = final_assignment[
                entity_id
            ]

        internal_weight: dict[
            int,
            float,
        ] = defaultdict(
            float
        )

        community_degree: dict[
            int,
            float,
        ] = defaultdict(
            float
        )

        for node_id in (
            original_graph.nodes
        ):

            community_id = (
                node_to_community[
                    node_id
                ]
            )

            community_degree[
                community_id
            ] += degrees[
                node_id
            ]

        for (
            source,
            target,
            weight,
        ) in original_graph.edges:

            source_community = (
                node_to_community[
                    source
                ]
            )

            target_community = (
                node_to_community[
                    target
                ]
            )

            if (
                source_community
                ==
                target_community
            ):

                internal_weight[
                    source_community
                ] += weight

        modularity = 0.0

        for community_id in (
            community_degree
        ):

            modularity += (
                internal_weight.get(
                    community_id,
                    0.0,
                )
                /
                total_weight
                -
                (
                    resolution
                    *
                    (
                        community_degree[
                            community_id
                        ]
                        /
                        (
                            2.0
                            *
                            total_weight
                        )
                    )
                    ** 2
                )
            )

        return modularity