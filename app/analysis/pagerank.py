"""
PageRank graph analysis.

Calculates global Entity importance using the
PageRank random-walk model.

Responsibilities:

- calculate PageRank on NormalizedEntityGraph
- support directed graphs
- support undirected graph projections
- support analytical edge weights
- preserve parallel-edge influence when requested
- handle dangling nodes correctly
- handle self-loops
- provide convergence diagnostics
- provide deterministic ranking

Does NOT:

- query the database
- modify graph objects
- normalize raw EntityGraph objects
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
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PageRankConfig:
    """
    PageRank numerical configuration.
    """

    damping_factor: float = 0.85

    tolerance: float = 1e-10

    max_iterations: int = 200

    def __post_init__(
        self,
    ) -> None:

        damping = float(
            self.damping_factor
        )

        if (
            not isfinite(
                damping
            )
            or not (
                0.0
                <
                damping
                <
                1.0
            )
        ):

            raise ValueError(
                "damping_factor must be "
                "strictly between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "damping_factor",
            damping,
        )

        tolerance = float(
            self.tolerance
        )

        if (
            not isfinite(
                tolerance
            )
            or tolerance
            <=
            0.0
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
                self.max_iterations,
                int,
            )
            or
            self.max_iterations
            <
            1
        ):

            raise ValueError(
                "max_iterations must be "
                "a positive integer."
            )


# ==========================================================
# Node result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PageRankNodeResult:
    """
    PageRank score for one Entity.
    """

    entity_id: UUID

    score: float

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

        score = float(
            self.score
        )

        if (
            not isfinite(
                score
            )
            or score < 0.0
        ):

            raise ValueError(
                "PageRank score must be "
                "finite and non-negative."
            )

        object.__setattr__(
            self,
            "score",
            score,
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PageRankResult:
    """
    Complete PageRank result and convergence metadata.
    """

    scores: tuple[
        PageRankNodeResult,
        ...,
    ]

    damping_factor: float

    iterations: int

    converged: bool

    residual: float

    node_count: int

    edge_count: int

    source_edge_count: int

    def __post_init__(
        self,
    ) -> None:

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
                PageRankNodeResult,
            ):

                raise TypeError(
                    "scores must contain only "
                    "PageRankNodeResult objects."
                )

            if score.entity_id in seen:

                raise ValueError(
                    "Duplicate Entity PageRank result."
                )

            seen.add(
                score.entity_id
            )

        damping = float(
            self.damping_factor
        )

        if (
            not isfinite(
                damping
            )
            or not (
                0.0
                <
                damping
                <
                1.0
            )
        ):

            raise ValueError(
                "Invalid damping_factor."
            )

        object.__setattr__(
            self,
            "damping_factor",
            damping,
        )

        if (
            not isinstance(
                self.iterations,
                int,
            )
            or
            self.iterations < 0
        ):

            raise ValueError(
                "iterations must be "
                "a non-negative integer."
            )

        if not isinstance(
            self.converged,
            bool,
        ):

            raise TypeError(
                "converged must be bool."
            )

        residual = float(
            self.residual
        )

        if (
            not isfinite(
                residual
            )
            or residual < 0.0
        ):

            raise ValueError(
                "residual must be finite "
                "and non-negative."
            )

        object.__setattr__(
            self,
            "residual",
            residual,
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

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        entity_id: UUID,
    ) -> PageRankNodeResult:
        """
        Return PageRank for one Entity.
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
        PageRankNodeResult,
    ]:

        return {
            item.entity_id: item
            for item
            in self.scores
        }

    # ==========================================================
    # Probability diagnostics
    # ==========================================================

    @property
    def total_score(
        self,
    ) -> float:

        return sum(
            item.score
            for item
            in self.scores
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top(
        self,
        limit: int = 10,
    ) -> tuple[
        PageRankNodeResult,
        ...,
    ]:
        """
        Return highest PageRank Entities.

        UUID resolves equal-score ties deterministically.
        """

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
            key=lambda item: (
                -item.score,
                str(
                    item.entity_id
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


class PageRankService:
    """
    Calculate PageRank from a normalized graph.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
        config: (
            PageRankConfig
            | None
        ) = None,
    ) -> PageRankResult:
        """
        Calculate PageRank.

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
            or PageRankConfig()
        )

        if not isinstance(
            config,
            PageRankConfig,
        ):

            raise TypeError(
                "config must be PageRankConfig."
            )

        node_ids = tuple(
            sorted(
                graph.nodes,
                key=str,
            )
        )

        node_count = len(
            node_ids
        )

        # ======================================================
        # Empty graph
        # ======================================================

        if node_count == 0:

            return PageRankResult(
                scores=(),
                damping_factor=(
                    config.damping_factor
                ),
                iterations=0,
                converged=True,
                residual=0.0,
                node_count=0,
                edge_count=(
                    graph.edge_count
                ),
                source_edge_count=(
                    graph.source_edge_count
                ),
            )

        transitions = (
            self._build_transition_weights(
                graph,
                node_ids=node_ids,
            )
        )

        outgoing_weight = {
            entity_id: sum(
                transitions[
                    entity_id
                ].values()
            )
            for entity_id
            in node_ids
        }

        initial_score = (
            1.0
            /
            node_count
        )

        ranks = {
            entity_id: initial_score
            for entity_id
            in node_ids
        }

        damping = (
            config.damping_factor
        )

        converged = False

        residual = 0.0

        iterations = 0

        # ======================================================
        # Power iteration
        # ======================================================

        for iteration in range(
            1,
            config.max_iterations
            +
            1,
        ):

            iterations = (
                iteration
            )

            dangling_mass = sum(
                ranks[
                    entity_id
                ]
                for entity_id
                in node_ids
                if (
                    outgoing_weight[
                        entity_id
                    ]
                    <=
                    0.0
                )
            )

            teleport = (
                (
                    1.0
                    -
                    damping
                )
                /
                node_count
            )

            dangling_share = (
                damping
                *
                dangling_mass
                /
                node_count
            )

            new_ranks = {
                entity_id: (
                    teleport
                    +
                    dangling_share
                )
                for entity_id
                in node_ids
            }

            for source_id in node_ids:

                total_weight = (
                    outgoing_weight[
                        source_id
                    ]
                )

                if total_weight <= 0.0:

                    continue

                distributable = (
                    damping
                    *
                    ranks[
                        source_id
                    ]
                )

                for (
                    target_id,
                    weight,
                ) in sorted(
                    transitions[
                        source_id
                    ].items(),
                    key=lambda item: str(
                        item[
                            0
                        ]
                    ),
                ):

                    if weight <= 0.0:

                        continue

                    new_ranks[
                        target_id
                    ] += (
                        distributable
                        *
                        (
                            weight
                            /
                            total_weight
                        )
                    )

            # ==================================================
            # Numerical normalization
            # ==================================================

            total = sum(
                new_ranks.values()
            )

            if total <= 0.0:

                raise RuntimeError(
                    "PageRank iteration produced "
                    "zero probability mass."
                )

            for entity_id in node_ids:

                new_ranks[
                    entity_id
                ] /= total

            residual = sum(
                abs(
                    new_ranks[
                        entity_id
                    ]
                    -
                    ranks[
                        entity_id
                    ]
                )
                for entity_id
                in node_ids
            )

            ranks = (
                new_ranks
            )

            if (
                residual
                <=
                config.tolerance
            ):

                converged = True

                break

        scores = tuple(
            PageRankNodeResult(
                entity_id=entity_id,
                score=ranks[
                    entity_id
                ],
            )
            for entity_id
            in node_ids
        )

        return PageRankResult(
            scores=scores,
            damping_factor=damping,
            iterations=iterations,
            converged=converged,
            residual=residual,
            node_count=node_count,
            edge_count=(
                graph.edge_count
            ),
            source_edge_count=(
                graph.source_edge_count
            ),
        )

    # ==========================================================
    # Transition graph
    # ==========================================================

    def _build_transition_weights(
        self,
        graph: NormalizedEntityGraph,
        *,
        node_ids: tuple[
            UUID,
            ...,
        ],
    ) -> dict[
        UUID,
        dict[
            UUID,
            float,
        ],
    ]:
        """
        Build weighted random-walk transitions.

        DIRECTED:
            source -> target

        UNDIRECTED:
            source <-> target

        Parallel normalized edges add transition weight.

        Self-loop contributes one transition to itself.
        """

        transitions: dict[
            UUID,
            dict[
                UUID,
                float,
            ],
        ] = {
            entity_id: {}
            for entity_id
            in node_ids
        }

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
                    "PageRank edge weights must "
                    "be finite and non-negative."
                )

            source_id = (
                edge.source_id
            )

            target_id = (
                edge.target_id
            )

            # Zero-weight edges are structural but do
            # not contribute random-walk probability.
            if weight <= 0.0:

                continue

            self._add_transition(
                transitions,
                source_id=source_id,
                target_id=target_id,
                weight=weight,
            )

            if (
                graph.semantics.direction
                ==
                GraphDirection.UNDIRECTED
                and
                source_id
                !=
                target_id
            ):

                self._add_transition(
                    transitions,
                    source_id=target_id,
                    target_id=source_id,
                    weight=weight,
                )

        return transitions

    # ==========================================================
    # Transition helper
    # ==========================================================

    @staticmethod
    def _add_transition(
        transitions: dict[
            UUID,
            dict[
                UUID,
                float,
            ],
        ],
        *,
        source_id: UUID,
        target_id: UUID,
        weight: float,
    ) -> None:

        transitions[
            source_id
        ][
            target_id
        ] = (
            transitions[
                source_id
            ].get(
                target_id,
                0.0,
            )
            +
            weight
        )