"""
Connected-components graph analysis.

Detects structurally separated parts of a normalized
investigation graph.

Responsibilities:

- calculate connected components for undirected graphs
- calculate weakly connected components for directed graphs
- calculate strongly connected components for directed graphs
- preserve deterministic component ordering
- ignore parallel-edge multiplicity for connectivity
- handle self-loops safely
- handle isolated entities
- provide component lookup helpers

Does NOT:

- query the database
- modify graph objects
- detect Louvain communities
- calculate centrality
- perform link prediction
"""

from __future__ import annotations

from collections import deque

from dataclasses import dataclass

from enum import Enum

from uuid import UUID

from app.analysis.graph_contracts import (
    GraphDirection,
    GraphNeighborMode,
)

from app.analysis.graph_normalization import (
    NormalizedEntityGraph,
)


# ==========================================================
# Mode
# ==========================================================


class ConnectedComponentMode(
    str,
    Enum,
):
    """
    Connectivity interpretation.

    CONNECTED:
        Standard connected components.
        Valid only for UNDIRECTED graphs.

    WEAK:
        Directed edges are treated as undirected.

    STRONG:
        Every Entity inside a component must be
        mutually reachable through directed paths.
    """

    CONNECTED = "connected"

    WEAK = "weak"

    STRONG = "strong"


# ==========================================================
# Component
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphComponent:
    """
    One deterministic graph component.
    """

    entity_ids: tuple[
        UUID,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

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
                    "Component Entity IDs "
                    "must be UUID."
                )

            if entity_id in seen:

                raise ValueError(
                    "Component cannot contain "
                    "duplicate Entity IDs."
                )

            seen.add(
                entity_id
            )

            normalized.append(
                entity_id
            )

        if not normalized:

            raise ValueError(
                "Component cannot be empty."
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
    def is_isolated(
        self,
    ) -> bool:
        """
        Structurally isolated component.

        A singleton may still contain a self-loop,
        but it is disconnected from other Entities.
        """

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
class ConnectedComponentsResult:
    """
    Complete connectivity-analysis result.
    """

    direction: GraphDirection

    mode: ConnectedComponentMode

    components: tuple[
        GraphComponent,
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
            self.mode,
            ConnectedComponentMode,
        ):

            raise TypeError(
                "mode must be "
                "ConnectedComponentMode."
            )

        if not isinstance(
            self.components,
            tuple,
        ):

            raise TypeError(
                "components must be a tuple."
            )

        seen_entities: set[
            UUID
        ] = set()

        for component in self.components:

            if not isinstance(
                component,
                GraphComponent,
            ):

                raise TypeError(
                    "components must contain "
                    "GraphComponent objects."
                )

            for entity_id in (
                component.entity_ids
            ):

                if (
                    entity_id
                    in
                    seen_entities
                ):

                    raise ValueError(
                        "Entity appears in more "
                        "than one component."
                    )

                seen_entities.add(
                    entity_id
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
                seen_entities
            )
            !=
            self.node_count
        ):

            raise ValueError(
                "Components must cover "
                "every graph node exactly once."
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def component_count(
        self,
    ) -> int:

        return len(
            self.components
        )

    @property
    def largest_component_size(
        self,
    ) -> int:

        return max(
            (
                component.size
                for component
                in self.components
            ),
            default=0,
        )

    @property
    def isolated_component_count(
        self,
    ) -> int:

        return sum(
            1
            for component
            in self.components
            if component.is_isolated
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_component(
        self,
        entity_id: UUID,
    ) -> GraphComponent:
        """
        Return the component containing one Entity.
        """

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for component in self.components:

            if (
                entity_id
                in
                component.entity_ids
            ):

                return component

        raise KeyError(
            f"Unknown graph node: {entity_id}"
        )

    def same_component(
        self,
        first_entity_id: UUID,
        second_entity_id: UUID,
    ) -> bool:
        """
        Determine whether two Entities belong to the
        same component.
        """

        first_component = (
            self.get_component(
                first_entity_id
            )
        )

        second_component = (
            self.get_component(
                second_entity_id
            )
        )

        return (
            first_component
            ==
            second_component
        )


# ==========================================================
# Service
# ==========================================================


class ConnectedComponentsService:
    """
    Calculate graph connectivity components.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
        mode: (
            ConnectedComponentMode
            | None
        ) = None,
    ) -> ConnectedComponentsResult:
        """
        Calculate graph components.

        Default semantics:

            UNDIRECTED -> CONNECTED
            DIRECTED   -> WEAK

        The directed default intentionally preserves
        the broad connectivity meaning of the legacy
        ClusterAnalyzer.

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

        if mode is None:

            if (
                graph.semantics.direction
                ==
                GraphDirection.UNDIRECTED
            ):

                mode = (
                    ConnectedComponentMode
                    .CONNECTED
                )

            else:

                mode = (
                    ConnectedComponentMode
                    .WEAK
                )

        if not isinstance(
            mode,
            ConnectedComponentMode,
        ):

            raise TypeError(
                "mode must be "
                "ConnectedComponentMode."
            )

        self._validate_mode(
            graph=graph,
            mode=mode,
        )

        if (
            mode
            ==
            ConnectedComponentMode
            .STRONG
        ):

            raw_components = (
                self._strong_components(
                    graph
                )
            )

        else:

            raw_components = (
                self._bfs_components(
                    graph,
                    mode=mode,
                )
            )

        components = tuple(
            sorted(
                (
                    GraphComponent(
                        entity_ids=tuple(
                            component
                        )
                    )
                    for component
                    in raw_components
                ),
                key=self._component_sort_key,
            )
        )

        return (
            ConnectedComponentsResult(
                direction=(
                    graph.semantics.direction
                ),
                mode=mode,
                components=components,
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
    # Connected / weak components
    # ==========================================================

    def _bfs_components(
        self,
        graph: NormalizedEntityGraph,
        *,
        mode: ConnectedComponentMode,
    ) -> list[
        tuple[
            UUID,
            ...,
        ]
    ]:

        visited: set[
            UUID
        ] = set()

        components: list[
            tuple[
                UUID,
                ...,
            ]
        ] = []

        for start_id in sorted(
            graph.nodes,
            key=str,
        ):

            if start_id in visited:

                continue

            queue = deque(
                [
                    start_id
                ]
            )

            visited.add(
                start_id
            )

            component: list[
                UUID
            ] = []

            while queue:

                current = (
                    queue.popleft()
                )

                component.append(
                    current
                )

                neighbors = (
                    self._neighbors_for_component(
                        graph,
                        current,
                        mode=mode,
                    )
                )

                for neighbor in neighbors:

                    if (
                        neighbor
                        in
                        visited
                    ):

                        continue

                    visited.add(
                        neighbor
                    )

                    queue.append(
                        neighbor
                    )

            components.append(
                tuple(
                    sorted(
                        component,
                        key=str,
                    )
                )
            )

        return components

    # ==========================================================
    # Strong components
    #
    # Kosaraju algorithm.
    # ==========================================================

    def _strong_components(
        self,
        graph: NormalizedEntityGraph,
    ) -> list[
        tuple[
            UUID,
            ...,
        ]
    ]:
        """
        Calculate strongly connected components using
        deterministic iterative Kosaraju traversal.

        No recursion is used, avoiding recursion-depth
        problems on large investigations.
        """

        finish_order = (
            self._directed_finish_order(
                graph
            )
        )

        visited: set[
            UUID
        ] = set()

        components: list[
            tuple[
                UUID,
                ...,
            ]
        ] = []

        # Reverse finishing order, traverse transpose
        # graph through INCOMING edges.
        for start_id in reversed(
            finish_order
        ):

            if start_id in visited:

                continue

            component = (
                self._collect_transpose_component(
                    graph,
                    start_id=start_id,
                    visited=visited,
                )
            )

            components.append(
                component
            )

        return components

    # ==========================================================
    # Kosaraju first pass
    # ==========================================================

    def _directed_finish_order(
        self,
        graph: NormalizedEntityGraph,
    ) -> tuple[
        UUID,
        ...,
    ]:

        visited: set[
            UUID
        ] = set()

        finish_order: list[
            UUID
        ] = []

        for start_id in sorted(
            graph.nodes,
            key=str,
        ):

            if start_id in visited:

                continue

            # (node, expanded)
            stack: list[
                tuple[
                    UUID,
                    bool,
                ]
            ] = [
                (
                    start_id,
                    False,
                )
            ]

            while stack:

                (
                    current,
                    expanded,
                ) = stack.pop()

                if expanded:

                    finish_order.append(
                        current
                    )

                    continue

                if current in visited:

                    continue

                visited.add(
                    current
                )

                # Add post-order marker.
                stack.append(
                    (
                        current,
                        True,
                    )
                )

                neighbors = (
                    graph.unique_neighbors(
                        current,
                        mode=(
                            GraphNeighborMode
                            .OUTGOING
                        ),
                    )
                )

                # Stack is LIFO. Reverse ensures
                # smallest UUID is visited first.
                for neighbor in reversed(
                    neighbors
                ):

                    if (
                        neighbor
                        ==
                        current
                    ):

                        continue

                    if (
                        neighbor
                        not in
                        visited
                    ):

                        stack.append(
                            (
                                neighbor,
                                False,
                            )
                        )

        return tuple(
            finish_order
        )

    # ==========================================================
    # Kosaraju second pass
    # ==========================================================

    def _collect_transpose_component(
        self,
        graph: NormalizedEntityGraph,
        *,
        start_id: UUID,
        visited: set[
            UUID
        ],
    ) -> tuple[
        UUID,
        ...,
    ]:

        stack = [
            start_id
        ]

        visited.add(
            start_id
        )

        component: list[
            UUID
        ] = []

        while stack:

            current = (
                stack.pop()
            )

            component.append(
                current
            )

            neighbors = (
                graph.unique_neighbors(
                    current,
                    mode=(
                        GraphNeighborMode
                        .INCOMING
                    ),
                )
            )

            for neighbor in reversed(
                neighbors
            ):

                if (
                    neighbor
                    ==
                    current
                ):

                    continue

                if (
                    neighbor
                    in
                    visited
                ):

                    continue

                visited.add(
                    neighbor
                )

                stack.append(
                    neighbor
                )

        return tuple(
            sorted(
                component,
                key=str,
            )
        )

    # ==========================================================
    # Neighbor semantics
    # ==========================================================

    @staticmethod
    def _neighbors_for_component(
        graph: NormalizedEntityGraph,
        entity_id: UUID,
        *,
        mode: ConnectedComponentMode,
    ) -> tuple[
        UUID,
        ...,
    ]:

        # Standard undirected connected components.
        if (
            mode
            ==
            ConnectedComponentMode
            .CONNECTED
        ):

            neighbors = (
                graph.unique_neighbors(
                    entity_id,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
            )

        # Weak directed components deliberately ignore
        # orientation.
        elif (
            mode
            ==
            ConnectedComponentMode.WEAK
        ):

            neighbors = (
                graph.unique_neighbors(
                    entity_id,
                    mode=(
                        GraphNeighborMode.ALL
                    ),
                )
            )

        else:

            raise RuntimeError(
                "STRONG connectivity must use "
                "the SCC algorithm."
            )

        # Self-loops do not connect an Entity to a
        # different component.
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
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_mode(
        *,
        graph: NormalizedEntityGraph,
        mode: ConnectedComponentMode,
    ) -> None:

        direction = (
            graph.semantics.direction
        )

        if (
            direction
            ==
            GraphDirection.UNDIRECTED
        ):

            if (
                mode
                !=
                ConnectedComponentMode
                .CONNECTED
            ):

                raise ValueError(
                    "Undirected graphs require "
                    "CONNECTED component mode."
                )

            return

        # Directed graph.
        if (
            mode
            ==
            ConnectedComponentMode
            .CONNECTED
        ):

            raise ValueError(
                "Directed graphs require WEAK "
                "or STRONG component mode."
            )

    # ==========================================================
    # Deterministic ordering
    # ==========================================================

    @staticmethod
    def _component_sort_key(
        component: GraphComponent,
    ) -> tuple[
        int,
        tuple[
            str,
            ...,
        ],
    ]:
        """
        Largest components first.

        UUID sequence resolves equal-size ties.
        """

        return (
            -component.size,
            tuple(
                str(
                    entity_id
                )
                for entity_id
                in component.entity_ids
            ),
        )