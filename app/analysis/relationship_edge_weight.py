"""
Relationship / analytical edge weight model.

Converts one or more normalized Relationship-derived
graph edges into one correlation-safe structural
strength for an Entity pair.

Responsibilities:

- separate Relationship confidence from graph strength
- combine repeated relationship observations safely
- prevent linear parallel-edge inflation
- support relationship-type weighting
- preserve directed edge orientation
- canonicalize undirected Entity pairs
- provide deterministic edge-strength ranking
- preserve complete explainability of the calculation

Does NOT:

- query the database
- create or modify Relationship objects
- modify NormalizedEntityGraph
- treat repeated relationships as independent evidence
- calculate PageRank
- calculate centrality
- persist calculated strengths
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import (
    isfinite,
    prod,
)

from uuid import UUID

from app.analysis.graph_contracts import (
    GraphDirection,
)

from app.analysis.graph_normalization import (
    NormalizedEntityGraph,
    NormalizedGraphEdge,
)


# ==========================================================
# Relationship-type aggregation
# ==========================================================


class RelationshipTypeWeightAggregation(
    str,
    Enum,
):
    """
    How multiple relationship-type weights belonging
    to the same Entity pair are combined.

    MAX:
        strongest configured relationship semantics
        controls the pair.

    MEAN:
        average relationship-type factor.

    MIN:
        most conservative relationship-type factor.

    Default is MAX.

    Because all type factors are bounded to [0, 1],
    even MAX can never make an edge stronger than its
    confidence-derived strength.
    """

    MAX = "max"

    MEAN = "mean"

    MIN = "min"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RelationshipEdgeWeightConfig:
    """
    Analytical edge-weight configuration.

    repeat_bonus_weight:

        Controls how much repeated relationship
        observations may strengthen the strongest
        observation.

        0.0:
            repeated observations have no effect.

        1.0:
            full secondary noisy-OR contribution.

        Default 0.25 is intentionally conservative.

    default_type_weight:

        Weight applied when relationship type has no
        explicit custom value.

        Default 1.0 means no type-based downweighting.

    relationship_type_weights:

        Optional explicit mapping represented as
        deterministic tuple pairs:

            (
                ("messaged", 0.8),
                ("owns", 1.0),
            )

        Type weights are constrained to [0, 1].

        They may downweight a structural relationship
        but never inflate it above confidence-derived
        strength.
    """

    repeat_bonus_weight: float = 0.25

    default_type_weight: float = 1.0

    relationship_type_aggregation: (
        RelationshipTypeWeightAggregation
    ) = (
        RelationshipTypeWeightAggregation.MAX
    )

    relationship_type_weights: tuple[
        tuple[
            str,
            float,
        ],
        ...,
    ] = ()

    def __post_init__(
        self,
    ) -> None:

        repeat_bonus_weight = float(
            self.repeat_bonus_weight
        )

        if (
            not isfinite(
                repeat_bonus_weight
            )
            or not (
                0.0
                <= repeat_bonus_weight
                <= 1.0
            )
        ):

            raise ValueError(
                "repeat_bonus_weight must be "
                "between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "repeat_bonus_weight",
            repeat_bonus_weight,
        )

        default_type_weight = float(
            self.default_type_weight
        )

        if (
            not isfinite(
                default_type_weight
            )
            or not (
                0.0
                <= default_type_weight
                <= 1.0
            )
        ):

            raise ValueError(
                "default_type_weight must be "
                "between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "default_type_weight",
            default_type_weight,
        )

        if not isinstance(
            self.relationship_type_aggregation,
            RelationshipTypeWeightAggregation,
        ):

            raise TypeError(
                "relationship_type_aggregation must "
                "be RelationshipTypeWeightAggregation."
            )

        if not isinstance(
            self.relationship_type_weights,
            tuple,
        ):

            raise TypeError(
                "relationship_type_weights must "
                "be a tuple."
            )

        normalized_weights: list[
            tuple[
                str,
                float,
            ]
        ] = []

        seen_types: set[
            str
        ] = set()

        for item in (
            self.relationship_type_weights
        ):

            if (
                not isinstance(
                    item,
                    tuple,
                )
                or len(
                    item
                )
                != 2
            ):

                raise TypeError(
                    "Each relationship type weight "
                    "must be a (type, weight) tuple."
                )

            (
                relationship_type,
                weight,
            ) = item

            if not isinstance(
                relationship_type,
                str,
            ):

                raise TypeError(
                    "Relationship type key "
                    "must be string."
                )

            normalized_type = (
                relationship_type
                .strip()
                .lower()
            )

            if not normalized_type:

                raise ValueError(
                    "Relationship type key "
                    "cannot be empty."
                )

            if (
                normalized_type
                in seen_types
            ):

                raise ValueError(
                    "Duplicate relationship type "
                    f"weight: {normalized_type}"
                )

            value = float(
                weight
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
                    "Relationship type weight must "
                    "be between 0.0 and 1.0."
                )

            seen_types.add(
                normalized_type
            )

            normalized_weights.append(
                (
                    normalized_type,
                    value,
                )
            )

        normalized_weights.sort(
            key=lambda item: (
                item[
                    0
                ]
            )
        )

        object.__setattr__(
            self,
            "relationship_type_weights",
            tuple(
                normalized_weights
            ),
        )

    # ==========================================================
    # Type lookup
    # ==========================================================

    def weight_for_type(
        self,
        relationship_type: str,
    ) -> float:

        if not isinstance(
            relationship_type,
            str,
        ):

            raise TypeError(
                "relationship_type must "
                "be string."
            )

        normalized_type = (
            relationship_type
            .strip()
            .lower()
        )

        if not normalized_type:

            raise ValueError(
                "relationship_type cannot "
                "be empty."
            )

        for (
            type_name,
            weight,
        ) in (
            self.relationship_type_weights
        ):

            if (
                type_name
                ==
                normalized_type
            ):

                return weight

        return (
            self.default_type_weight
        )


# ==========================================================
# Pair assessment
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RelationshipEdgeStrength:
    """
    Analytical strength of one structural Entity pair.

    source_edge_count:
        Number of original Relationship-derived edges
        represented by this structural pair.

    strongest_confidence:
        Dominant Relationship confidence.

    secondary_support:
        Correlation-aware noisy-OR of every confidence
        except the strongest one.

    repeat_bonus:
        Limited contribution from repeated observations.

    confidence_strength:
        Strength before relationship-type adjustment.

    type_factor:
        Aggregated semantic factor for relationship
        types.

    final_strength:
        Final analytical graph edge strength.
    """

    source_entity_id: UUID

    target_entity_id: UUID

    direction: GraphDirection

    relationship_types: tuple[
        str,
        ...,
    ]

    source_edge_count: int

    confidences: tuple[
        float,
        ...,
    ]

    strongest_confidence: float

    secondary_support: float

    repeat_bonus: float

    confidence_strength: float

    type_factor: float

    final_strength: float

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

        if not isinstance(
            self.direction,
            GraphDirection,
        ):

            raise TypeError(
                "direction must be "
                "GraphDirection."
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
                    )
                    .strip()
                    .lower()
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
                "At least one relationship type "
                "is required."
            )

        object.__setattr__(
            self,
            "relationship_types",
            normalized_types,
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
                    "Confidence values must "
                    "be between 0.0 and 1.0."
                )

            normalized_confidences.append(
                value
            )

        normalized_confidences.sort(
            reverse=True
        )

        if (
            len(
                normalized_confidences
            )
            !=
            self.source_edge_count
        ):

            raise ValueError(
                "confidence count must match "
                "source_edge_count."
            )

        object.__setattr__(
            self,
            "confidences",
            tuple(
                normalized_confidences
            ),
        )

        for field_name in (
            "strongest_confidence",
            "secondary_support",
            "repeat_bonus",
            "confidence_strength",
            "type_factor",
            "final_strength",
        ):

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

        if (
            abs(
                self.strongest_confidence
                -
                max(
                    normalized_confidences
                )
            )
            >
            1e-12
        ):

            raise ValueError(
                "strongest_confidence does not "
                "match confidence observations."
            )

    # ==========================================================
    # Diagnostics
    # ==========================================================

    @property
    def repeated_observation_count(
        self,
    ) -> int:

        return max(
            0,
            (
                self.source_edge_count
                -
                1
            ),
        )

    @property
    def relationship_type_count(
        self,
    ) -> int:

        return len(
            self.relationship_types
        )

    @property
    def has_repeated_observations(
        self,
    ) -> bool:

        return (
            self.source_edge_count
            >
            1
        )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RelationshipEdgeWeightResult:
    """
    Complete relationship edge-strength analysis.
    """

    direction: GraphDirection

    assessments: tuple[
        RelationshipEdgeStrength,
        ...,
    ]

    input_normalized_edge_count: int

    source_edge_count: int

    structural_pair_count: int

    collapsed_normalized_edge_count: int

    repeat_bonus_weight: float

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
            self.assessments,
            tuple,
        ):

            raise TypeError(
                "assessments must be a tuple."
            )

        seen_pairs: set[
            tuple[
                UUID,
                UUID,
            ]
        ] = set()

        for assessment in self.assessments:

            if not isinstance(
                assessment,
                RelationshipEdgeStrength,
            ):

                raise TypeError(
                    "assessments must contain "
                    "RelationshipEdgeStrength."
                )

            pair = (
                assessment.source_entity_id,
                assessment.target_entity_id,
            )

            if pair in seen_pairs:

                raise ValueError(
                    "Duplicate structural edge pair."
                )

            seen_pairs.add(
                pair
            )

        for field_name in (
            "input_normalized_edge_count",
            "source_edge_count",
            "structural_pair_count",
            "collapsed_normalized_edge_count",
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
            self.structural_pair_count
            !=
            len(
                self.assessments
            )
        ):

            raise ValueError(
                "structural_pair_count must match "
                "assessment count."
            )

        repeat_bonus_weight = float(
            self.repeat_bonus_weight
        )

        if (
            not isfinite(
                repeat_bonus_weight
            )
            or not (
                0.0
                <= repeat_bonus_weight
                <= 1.0
            )
        ):

            raise ValueError(
                "repeat_bonus_weight must be "
                "between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "repeat_bonus_weight",
            repeat_bonus_weight,
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> RelationshipEdgeStrength:
        """
        Return edge strength for one structural pair.

        UNDIRECTED:
            pair order normalized automatically.

        DIRECTED:
            orientation preserved.
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

            (
                source_entity_id,
                target_entity_id,
            ) = sorted(
                (
                    source_entity_id,
                    target_entity_id,
                ),
                key=str,
            )

        for assessment in self.assessments:

            if (
                assessment.source_entity_id
                ==
                source_entity_id
                and
                assessment.target_entity_id
                ==
                target_entity_id
            ):

                return assessment

        raise KeyError(
            "Structural edge pair not found."
        )

    # ==========================================================
    # Strength mapping
    # ==========================================================

    @property
    def strength_map(
        self,
    ) -> dict[
        tuple[
            UUID,
            UUID,
        ],
        float,
    ]:

        return {
            (
                assessment.source_entity_id,
                assessment.target_entity_id,
            ): assessment.final_strength
            for assessment
            in self.assessments
        }

    # ==========================================================
    # Ranking
    # ==========================================================

    def top(
        self,
        limit: int = 10,
    ) -> tuple[
        RelationshipEdgeStrength,
        ...,
    ]:
        """
        Highest-strength structural relationships.
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
            self.assessments,
            key=lambda assessment: (
                -assessment.final_strength,
                -assessment.confidence_strength,
                str(
                    assessment.source_entity_id
                ),
                str(
                    assessment.target_entity_id
                ),
            ),
        )

        return tuple(
            ordered[
                :limit
            ]
        )


# ==========================================================
# Internal aggregation group
# ==========================================================


@dataclass(
    slots=True,
)
class _RelationshipEdgeGroup:
    """
    Internal mutable pair aggregation.
    """

    source_entity_id: UUID

    target_entity_id: UUID

    relationship_types: set[
        str
    ]

    confidences: list[
        float
    ]

    source_edge_count: int = 0


# ==========================================================
# Service
# ==========================================================


class RelationshipEdgeWeightService:
    """
    Calculate correlation-safe structural edge strength
    from NormalizedEntityGraph.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: NormalizedEntityGraph,
        config: (
            RelationshipEdgeWeightConfig
            | None
        ) = None,
    ) -> RelationshipEdgeWeightResult:
        """
        Calculate one analytical strength for every
        structural Entity pair.

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
            or RelationshipEdgeWeightConfig()
        )

        if not isinstance(
            config,
            RelationshipEdgeWeightConfig,
        ):

            raise TypeError(
                "config must be "
                "RelationshipEdgeWeightConfig."
            )

        groups = self._group_edges(
            graph
        )

        assessments: list[
            RelationshipEdgeStrength
        ] = []

        for pair in sorted(
            groups,
            key=lambda item: (
                str(
                    item[
                        0
                    ]
                ),
                str(
                    item[
                        1
                    ]
                ),
            ),
        ):

            assessments.append(
                self._score_group(
                    groups[
                        pair
                    ],
                    direction=(
                        graph.semantics.direction
                    ),
                    config=config,
                )
            )

        assessments_tuple = tuple(
            assessments
        )

        source_edge_count = sum(
            assessment.source_edge_count
            for assessment
            in assessments_tuple
        )

        return RelationshipEdgeWeightResult(
            direction=(
                graph.semantics.direction
            ),
            assessments=(
                assessments_tuple
            ),
            input_normalized_edge_count=(
                graph.edge_count
            ),
            source_edge_count=(
                source_edge_count
            ),
            structural_pair_count=len(
                assessments_tuple
            ),
            collapsed_normalized_edge_count=max(
                0,
                (
                    graph.edge_count
                    -
                    len(
                        assessments_tuple
                    )
                ),
            ),
            repeat_bonus_weight=(
                config.repeat_bonus_weight
            ),
        )

    # ==========================================================
    # Pair grouping
    # ==========================================================

    def _group_edges(
        self,
        graph: NormalizedEntityGraph,
    ) -> dict[
        tuple[
            UUID,
            UUID,
        ],
        _RelationshipEdgeGroup,
    ]:

        groups: dict[
            tuple[
                UUID,
                UUID,
            ],
            _RelationshipEdgeGroup,
        ] = {}

        for edge in graph.edges:

            self._validate_normalized_edge(
                edge
            )

            source_id = (
                edge.source_id
            )

            target_id = (
                edge.target_id
            )

            if (
                graph.semantics.direction
                ==
                GraphDirection.UNDIRECTED
            ):

                (
                    source_id,
                    target_id,
                ) = sorted(
                    (
                        source_id,
                        target_id,
                    ),
                    key=str,
                )

            pair = (
                source_id,
                target_id,
            )

            group = groups.get(
                pair
            )

            if group is None:

                group = (
                    _RelationshipEdgeGroup(
                        source_entity_id=(
                            source_id
                        ),
                        target_entity_id=(
                            target_id
                        ),
                        relationship_types=set(),
                        confidences=[],
                        source_edge_count=0,
                    )
                )

                groups[
                    pair
                ] = group

            for relationship_type in (
                edge.relationship_types
            ):

                normalized_type = (
                    str(
                        relationship_type
                    )
                    .strip()
                    .lower()
                )

                if normalized_type:

                    group.relationship_types.add(
                        normalized_type
                    )

            group.confidences.extend(
                float(
                    confidence
                )
                for confidence
                in edge.confidences
            )

            group.source_edge_count += (
                edge.source_edge_count
            )

        # Structural integrity check.
        for group in groups.values():

            if (
                len(
                    group.confidences
                )
                !=
                group.source_edge_count
            ):

                raise ValueError(
                    "Grouped confidence count "
                    "does not match source edge count."
                )

            if not group.relationship_types:

                raise ValueError(
                    "Grouped edge has no "
                    "relationship type."
                )

        return groups

    # ==========================================================
    # Pair scoring
    # ==========================================================

    def _score_group(
        self,
        group: _RelationshipEdgeGroup,
        *,
        direction: GraphDirection,
        config: RelationshipEdgeWeightConfig,
    ) -> RelationshipEdgeStrength:

        confidences = sorted(
            (
                self._clamp01(
                    confidence
                )
                for confidence
                in group.confidences
            ),
            reverse=True,
        )

        if not confidences:

            raise ValueError(
                "Relationship edge group "
                "has no confidences."
            )

        strongest_confidence = (
            confidences[
                0
            ]
        )

        secondary_confidences = (
            confidences[
                1:
            ]
        )

        secondary_support = (
            self._noisy_or(
                secondary_confidences
            )
        )

        repeat_bonus = (
            (
                1.0
                -
                strongest_confidence
            )
            *
            secondary_support
            *
            config.repeat_bonus_weight
        )

        confidence_strength = (
            self._clamp01(
                strongest_confidence
                +
                repeat_bonus
            )
        )

        relationship_types = tuple(
            sorted(
                group.relationship_types
            )
        )

        type_weights = [
            config.weight_for_type(
                relationship_type
            )
            for relationship_type
            in relationship_types
        ]

        type_factor = (
            self._aggregate_type_weights(
                type_weights,
                mode=(
                    config
                    .relationship_type_aggregation
                ),
            )
        )

        final_strength = (
            self._clamp01(
                confidence_strength
                *
                type_factor
            )
        )

        return RelationshipEdgeStrength(
            source_entity_id=(
                group.source_entity_id
            ),
            target_entity_id=(
                group.target_entity_id
            ),
            direction=direction,
            relationship_types=(
                relationship_types
            ),
            source_edge_count=(
                group.source_edge_count
            ),
            confidences=tuple(
                confidences
            ),
            strongest_confidence=(
                strongest_confidence
            ),
            secondary_support=(
                secondary_support
            ),
            repeat_bonus=(
                repeat_bonus
            ),
            confidence_strength=(
                confidence_strength
            ),
            type_factor=(
                type_factor
            ),
            final_strength=(
                final_strength
            ),
        )

    # ==========================================================
    # Relationship-type aggregation
    # ==========================================================

    @staticmethod
    def _aggregate_type_weights(
        weights: list[
            float
        ],
        *,
        mode: (
            RelationshipTypeWeightAggregation
        ),
    ) -> float:

        if not weights:

            return 1.0

        if (
            mode
            ==
            RelationshipTypeWeightAggregation
            .MAX
        ):

            return max(
                weights
            )

        if (
            mode
            ==
            RelationshipTypeWeightAggregation
            .MIN
        ):

            return min(
                weights
            )

        return (
            sum(
                weights
            )
            /
            len(
                weights
            )
        )

    # ==========================================================
    # Noisy OR
    # ==========================================================

    @staticmethod
    def _noisy_or(
        values: list[
            float
        ],
    ) -> float:
        """
        Combine secondary observations.

        Used only INSIDE a capped repeat bonus.

        Therefore repeated relationships cannot receive
        unrestricted noisy-OR strength.
        """

        if not values:

            return 0.0

        complement_product = prod(
            (
                1.0
                -
                RelationshipEdgeWeightService
                ._clamp01(
                    value
                )
            )
            for value
            in values
        )

        return (
            RelationshipEdgeWeightService
            ._clamp01(
                1.0
                -
                complement_product
            )
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_normalized_edge(
        edge: NormalizedGraphEdge,
    ) -> None:

        if not isinstance(
            edge,
            NormalizedGraphEdge,
        ):

            raise TypeError(
                "Expected NormalizedGraphEdge."
            )

    # ==========================================================
    # Numeric helpers
    # ==========================================================

    @staticmethod
    def _clamp01(
        value: float,
    ) -> float:

        value = float(
            value
        )

        if not isfinite(
            value
        ):

            raise ValueError(
                "Strength value must be finite."
            )

        return min(
            1.0,
            max(
                0.0,
                value,
            ),
        )