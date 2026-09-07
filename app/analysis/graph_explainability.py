"""
Graph analysis explainability and graph signals.

Transforms UnifiedGraphAnalysisResult into deterministic,
human-readable analytical explanations.

Responsibilities:

- explain graph-level analytical results
- explain Entity centrality and structural position
- explain pairwise Entity graph relationships
- expose graph-native analytical signals
- explain direct relationship strength
- explain connected-component membership
- explain Louvain community membership
- explain link-prediction metrics
- preserve mathematical score separation
- remain deterministic

Important semantic boundary:

Graph signals describe graph structure.

They are NOT:

- Evidence signals
- Relationship objects
- Entity Resolution signals
- automatic identity evidence
- database mutations

Does NOT:

- query the database
- create Relationships
- merge Entities
- modify analysis results
- combine metrics into one score
- automatically feed Entity Resolution
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import isfinite

from uuid import UUID

from app.analysis.link_prediction import (
    LinkPredictionCandidate,
)

from app.analysis.relationship_edge_weight import (
    RelationshipEdgeStrength,
)

from app.analysis.unified_graph_analysis import (
    GraphEntityAnalysisResult,
    UnifiedGraphAnalysisResult,
)


# ==========================================================
# Signal scope
# ==========================================================


class GraphSignalScope(
    str,
    Enum,
):
    """
    Structural scope of a graph signal.
    """

    GRAPH = "graph"

    ENTITY = "entity"

    PAIR = "pair"


# ==========================================================
# Signal type
# ==========================================================


class GraphSignalType(
    str,
    Enum,
):
    """
    Explainable graph-native analytical signal types.

    These names deliberately describe structure rather
    than truth or identity.
    """

    # Graph-level
    DENSITY = "density"

    COMPONENT_COUNT = (
        "component_count"
    )

    COMMUNITY_COUNT = (
        "community_count"
    )

    MODULARITY = "modularity"

    LINK_PREDICTION_COUNT = (
        "link_prediction_count"
    )

    STRUCTURAL_PAIR_COUNT = (
        "structural_pair_count"
    )

    # Entity-level
    DEGREE_CENTRALITY = (
        "degree_centrality"
    )

    PAGERANK = "pagerank"

    BETWEENNESS_CENTRALITY = (
        "betweenness_centrality"
    )

    BRIDGE_ROLE = "bridge_role"

    ISOLATED_ENTITY = (
        "isolated_entity"
    )

    # Pair-level
    DIRECT_RELATIONSHIP = (
        "direct_relationship"
    )

    SAME_COMPONENT = (
        "same_component"
    )

    DIFFERENT_COMPONENT = (
        "different_component"
    )

    SAME_COMMUNITY = (
        "same_community"
    )

    DIFFERENT_COMMUNITY = (
        "different_community"
    )

    COMMON_NEIGHBORS = (
        "common_neighbors"
    )

    JACCARD = "jaccard"

    ADAMIC_ADAR = "adamic_adar"


# ==========================================================
# Generic graph signal
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphAnalysisSignal:
    """
    One graph-native analytical observation.

    value:

        Raw mathematical value.

    normalized_value:

        Optional value in [0, 1] when the underlying
        metric naturally has a normalized form.

    metadata:

        Deterministic string metadata.

    A GraphAnalysisSignal is NOT an EntityResolutionSignal.
    """

    scope: GraphSignalScope

    signal_type: GraphSignalType

    value: float

    normalized_value: (
        float
        | None
    )

    reason: str

    subject_entity_id: (
        UUID
        | None
    ) = None

    related_entity_id: (
        UUID
        | None
    ) = None

    metadata: tuple[
        tuple[
            str,
            str,
        ],
        ...,
    ] = ()

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.scope,
            GraphSignalScope,
        ):

            raise TypeError(
                "scope must be "
                "GraphSignalScope."
            )

        if not isinstance(
            self.signal_type,
            GraphSignalType,
        ):

            raise TypeError(
                "signal_type must be "
                "GraphSignalType."
            )

        value = float(
            self.value
        )

        if not isfinite(
            value
        ):

            raise ValueError(
                "Graph signal value "
                "must be finite."
            )

        object.__setattr__(
            self,
            "value",
            value,
        )

        if (
            self.normalized_value
            is not None
        ):

            normalized_value = float(
                self.normalized_value
            )

            if (
                not isfinite(
                    normalized_value
                )
                or not (
                    0.0
                    <= normalized_value
                    <= 1.0
                )
            ):

                raise ValueError(
                    "normalized_value must be "
                    "between 0.0 and 1.0."
                )

            object.__setattr__(
                self,
                "normalized_value",
                normalized_value,
            )

        if (
            not isinstance(
                self.reason,
                str,
            )
            or not self.reason.strip()
        ):

            raise ValueError(
                "reason cannot be empty."
            )

        object.__setattr__(
            self,
            "reason",
            self.reason.strip(),
        )

        self._validate_scope()

        if not isinstance(
            self.metadata,
            tuple,
        ):

            raise TypeError(
                "metadata must be a tuple."
            )

        normalized_metadata: list[
            tuple[
                str,
                str,
            ]
        ] = []

        seen_keys: set[
            str
        ] = set()

        for item in self.metadata:

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
                    "metadata entries must be "
                    "(key, value) tuples."
                )

            key = str(
                item[
                    0
                ]
            ).strip()

            value_text = str(
                item[
                    1
                ]
            ).strip()

            if not key:

                raise ValueError(
                    "metadata key cannot "
                    "be empty."
                )

            if key in seen_keys:

                raise ValueError(
                    "Duplicate metadata key: "
                    f"{key}"
                )

            seen_keys.add(
                key
            )

            normalized_metadata.append(
                (
                    key,
                    value_text,
                )
            )

        normalized_metadata.sort(
            key=lambda item: (
                item[
                    0
                ]
            )
        )

        object.__setattr__(
            self,
            "metadata",
            tuple(
                normalized_metadata
            ),
        )

    # ==========================================================
    # Scope validation
    # ==========================================================

    def _validate_scope(
        self,
    ) -> None:

        if (
            self.scope
            ==
            GraphSignalScope.GRAPH
        ):

            if (
                self.subject_entity_id
                is not None
                or
                self.related_entity_id
                is not None
            ):

                raise ValueError(
                    "GRAPH signal cannot have "
                    "Entity IDs."
                )

            return

        if (
            self.scope
            ==
            GraphSignalScope.ENTITY
        ):

            if not isinstance(
                self.subject_entity_id,
                UUID,
            ):

                raise TypeError(
                    "ENTITY signal requires "
                    "subject_entity_id UUID."
                )

            if (
                self.related_entity_id
                is not None
            ):

                raise ValueError(
                    "ENTITY signal cannot have "
                    "related_entity_id."
                )

            return

        # PAIR
        if not isinstance(
            self.subject_entity_id,
            UUID,
        ):

            raise TypeError(
                "PAIR signal requires "
                "subject_entity_id UUID."
            )

        if not isinstance(
            self.related_entity_id,
            UUID,
        ):

            raise TypeError(
                "PAIR signal requires "
                "related_entity_id UUID."
            )

        if (
            self.subject_entity_id
            ==
            self.related_entity_id
        ):

            raise ValueError(
                "PAIR signal endpoints "
                "must be different Entities."
            )

    # ==========================================================
    # Metadata access
    # ==========================================================

    @property
    def metadata_dict(
        self,
    ) -> dict[
        str,
        str,
    ]:

        return dict(
            self.metadata
        )


# ==========================================================
# Metric rank
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphMetricRank:
    """
    Explainable rank for one Entity metric.

    Rank is 1-based.

    This is not a combined score.
    """

    metric: str

    value: float

    rank: int

    total_entities: int

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.metric,
                str,
            )
            or not self.metric.strip()
        ):

            raise ValueError(
                "metric cannot be empty."
            )

        object.__setattr__(
            self,
            "metric",
            self.metric.strip(),
        )

        value = float(
            self.value
        )

        if not isfinite(
            value
        ):

            raise ValueError(
                "Metric value must be finite."
            )

        object.__setattr__(
            self,
            "value",
            value,
        )

        if (
            not isinstance(
                self.rank,
                int,
            )
            or self.rank < 1
        ):

            raise ValueError(
                "rank must be positive."
            )

        if (
            not isinstance(
                self.total_entities,
                int,
            )
            or self.total_entities < 1
        ):

            raise ValueError(
                "total_entities must "
                "be positive."
            )

        if (
            self.rank
            >
            self.total_entities
        ):

            raise ValueError(
                "rank cannot exceed "
                "total_entities."
            )


# ==========================================================
# Entity explanation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphEntityExplanation:
    """
    Explainable graph position of one Entity.

    No aggregate importance score is calculated.
    """

    entity_id: UUID

    component_index: int

    component_size: int

    community_id: int

    community_size: int

    metric_ranks: tuple[
        GraphMetricRank,
        ...,
    ]

    signals: tuple[
        GraphAnalysisSignal,
        ...,
    ]

    reasons: tuple[
        str,
        ...,
    ]

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

        for field_name in (
            "component_index",
            "community_id",
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
                    "non-negative."
                )

        for field_name in (
            "component_size",
            "community_size",
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
                or value < 1
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "positive."
                )

        if not isinstance(
            self.metric_ranks,
            tuple,
        ):

            raise TypeError(
                "metric_ranks must be a tuple."
            )

        metrics: set[
            str
        ] = set()

        for metric_rank in (
            self.metric_ranks
        ):

            if not isinstance(
                metric_rank,
                GraphMetricRank,
            ):

                raise TypeError(
                    "metric_ranks must contain "
                    "GraphMetricRank."
                )

            if metric_rank.metric in metrics:

                raise ValueError(
                    "Duplicate metric rank."
                )

            metrics.add(
                metric_rank.metric
            )

        if not isinstance(
            self.signals,
            tuple,
        ):

            raise TypeError(
                "signals must be a tuple."
            )

        for signal in self.signals:

            if not isinstance(
                signal,
                GraphAnalysisSignal,
            ):

                raise TypeError(
                    "signals must contain "
                    "GraphAnalysisSignal."
                )

            if (
                signal.scope
                !=
                GraphSignalScope.ENTITY
            ):

                raise ValueError(
                    "Entity explanation contains "
                    "non-ENTITY signal."
                )

            if (
                signal.subject_entity_id
                !=
                self.entity_id
            ):

                raise ValueError(
                    "Entity signal subject mismatch."
                )

        if not isinstance(
            self.reasons,
            tuple,
        ):

            raise TypeError(
                "reasons must be a tuple."
            )

        for reason in self.reasons:

            if (
                not isinstance(
                    reason,
                    str,
                )
                or not reason.strip()
            ):

                raise ValueError(
                    "Explanation reasons cannot "
                    "be empty."
                )

    # ==========================================================
    # Metric lookup
    # ==========================================================

    def get_metric_rank(
        self,
        metric: str,
    ) -> GraphMetricRank:

        if not isinstance(
            metric,
            str,
        ):

            raise TypeError(
                "metric must be string."
            )

        for metric_rank in (
            self.metric_ranks
        ):

            if (
                metric_rank.metric
                ==
                metric
            ):

                return metric_rank

        raise KeyError(
            f"Metric rank not found: {metric}"
        )


# ==========================================================
# Pair explanation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphPairExplanation:
    """
    Explainable structural relationship between
    two Entities.

    This object describes association structure only.

    It must NOT be interpreted as identity evidence.
    """

    source_entity_id: UUID

    target_entity_id: UUID

    direct_edge: (
        RelationshipEdgeStrength
        | None
    )

    prediction: (
        LinkPredictionCandidate
        | None
    )

    same_component: bool

    component_mode: str

    same_community: bool

    signals: tuple[
        GraphAnalysisSignal,
        ...,
    ]

    reasons: tuple[
        str,
        ...,
    ]

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
                "Pair explanation requires "
                "different Entities."
            )

        if (
            self.direct_edge
            is not None
            and
            not isinstance(
                self.direct_edge,
                RelationshipEdgeStrength,
            )
        ):

            raise TypeError(
                "direct_edge must be "
                "RelationshipEdgeStrength or None."
            )

        if (
            self.prediction
            is not None
            and
            not isinstance(
                self.prediction,
                LinkPredictionCandidate,
            )
        ):

            raise TypeError(
                "prediction must be "
                "LinkPredictionCandidate or None."
            )

        # A confirmed structural edge is excluded from
        # missing-link prediction by Phase 3.8.
        if (
            self.direct_edge
            is not None
            and
            self.prediction
            is not None
        ):

            raise ValueError(
                "Pair cannot simultaneously be "
                "a direct edge and missing-link "
                "prediction."
            )

        if not isinstance(
            self.same_component,
            bool,
        ):

            raise TypeError(
                "same_component must be bool."
            )

        if (
            not isinstance(
                self.component_mode,
                str,
            )
            or not self.component_mode.strip()
        ):

            raise ValueError(
                "component_mode cannot be empty."
            )

        if not isinstance(
            self.same_community,
            bool,
        ):

            raise TypeError(
                "same_community must be bool."
            )

        if not isinstance(
            self.signals,
            tuple,
        ):

            raise TypeError(
                "signals must be a tuple."
            )

        for signal in self.signals:

            if not isinstance(
                signal,
                GraphAnalysisSignal,
            ):

                raise TypeError(
                    "signals must contain "
                    "GraphAnalysisSignal."
                )

            if (
                signal.scope
                !=
                GraphSignalScope.PAIR
            ):

                raise ValueError(
                    "Pair explanation contains "
                    "non-PAIR signal."
                )

            if (
                signal.subject_entity_id
                !=
                self.source_entity_id
                or
                signal.related_entity_id
                !=
                self.target_entity_id
            ):

                raise ValueError(
                    "Pair signal endpoint mismatch."
                )

        if not isinstance(
            self.reasons,
            tuple,
        ):

            raise TypeError(
                "reasons must be a tuple."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def has_direct_relationship(
        self,
    ) -> bool:

        return (
            self.direct_edge
            is not None
        )

    @property
    def has_link_prediction(
        self,
    ) -> bool:

        return (
            self.prediction
            is not None
        )


# ==========================================================
# Complete explainability result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphExplainabilityResult:
    """
    Graph-level and Entity-level explanations.

    Pair explanations are generated on demand because
    materializing every possible Entity pair would be
    O(N²).
    """

    graph_signals: tuple[
        GraphAnalysisSignal,
        ...,
    ]

    entity_explanations: tuple[
        GraphEntityExplanation,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.graph_signals,
            tuple,
        ):

            raise TypeError(
                "graph_signals must be a tuple."
            )

        for signal in (
            self.graph_signals
        ):

            if not isinstance(
                signal,
                GraphAnalysisSignal,
            ):

                raise TypeError(
                    "graph_signals must contain "
                    "GraphAnalysisSignal."
                )

            if (
                signal.scope
                !=
                GraphSignalScope.GRAPH
            ):

                raise ValueError(
                    "graph_signals contains "
                    "non-GRAPH signal."
                )

        if not isinstance(
            self.entity_explanations,
            tuple,
        ):

            raise TypeError(
                "entity_explanations must "
                "be a tuple."
            )

        seen: set[
            UUID
        ] = set()

        for explanation in (
            self.entity_explanations
        ):

            if not isinstance(
                explanation,
                GraphEntityExplanation,
            ):

                raise TypeError(
                    "entity_explanations must contain "
                    "GraphEntityExplanation."
                )

            if (
                explanation.entity_id
                in seen
            ):

                raise ValueError(
                    "Duplicate Entity explanation."
                )

            seen.add(
                explanation.entity_id
            )

    # ==========================================================
    # Entity lookup
    # ==========================================================

    def get_entity(
        self,
        entity_id: UUID,
    ) -> GraphEntityExplanation:

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for explanation in (
            self.entity_explanations
        ):

            if (
                explanation.entity_id
                ==
                entity_id
            ):

                return explanation

        raise KeyError(
            f"Entity explanation not found: "
            f"{entity_id}"
        )


# ==========================================================
# Service
# ==========================================================


class GraphExplainabilityService:
    """
    Build deterministic explanations from a completed
    UnifiedGraphAnalysisResult.
    """

    # ==========================================================
    # Complete graph explanation
    # ==========================================================

    def build(
        self,
        result: UnifiedGraphAnalysisResult,
    ) -> GraphExplainabilityResult:
        """
        Build graph-level and Entity-level explanations.

        Pair explanations remain on-demand.

        No database writes are performed.
        """

        self._validate_result(
            result
        )

        graph_signals = (
            self._build_graph_signals(
                result
            )
        )

        rank_maps = (
            self._build_rank_maps(
                result
            )
        )

        entity_explanations = tuple(
            self._explain_entity(
                result,
                entity,
                rank_maps=rank_maps,
            )
            for entity
            in result.entities
        )

        return GraphExplainabilityResult(
            graph_signals=(
                graph_signals
            ),
            entity_explanations=(
                entity_explanations
            ),
        )

    # ==========================================================
    # Public Entity explanation
    # ==========================================================

    def explain_entity(
        self,
        result: UnifiedGraphAnalysisResult,
        entity_id: UUID,
    ) -> GraphEntityExplanation:

        self._validate_result(
            result
        )

        entity = result.get_entity(
            entity_id
        )

        rank_maps = (
            self._build_rank_maps(
                result
            )
        )

        return self._explain_entity(
            result,
            entity,
            rank_maps=rank_maps,
        )

    # ==========================================================
    # Pair explanation
    # ==========================================================

    def explain_pair(
        self,
        result: UnifiedGraphAnalysisResult,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> GraphPairExplanation:
        """
        Explain structural relationship between two
        Entities.

        UNDIRECTED graph:
            pair order is canonicalized.

        DIRECTED graph:
            orientation is preserved.

        This method does NOT produce identity evidence.
        """

        self._validate_result(
            result
        )

        # Validate Entity existence.
        result.get_entity(
            source_entity_id
        )

        result.get_entity(
            target_entity_id
        )

        if (
            source_entity_id
            ==
            target_entity_id
        ):

            raise ValueError(
                "Pair explanation requires "
                "different Entities."
            )

        if (
            result.semantics.direction.value
            ==
            "undirected"
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

        direct_edge = (
            self._find_direct_edge(
                result,
                source_entity_id=(
                    source_entity_id
                ),
                target_entity_id=(
                    target_entity_id
                ),
            )
        )

        prediction = (
            self._find_prediction(
                result,
                source_entity_id=(
                    source_entity_id
                ),
                target_entity_id=(
                    target_entity_id
                ),
            )
        )

        same_component = (
            result.components
            .same_component(
                source_entity_id,
                target_entity_id,
            )
        )

        same_community = (
            result.communities
            .same_community(
                source_entity_id,
                target_entity_id,
            )
        )

        signals: list[
            GraphAnalysisSignal
        ] = []

        reasons: list[
            str
        ] = []

        # ======================================================
        # Direct edge
        # ======================================================

        if direct_edge is not None:

            signals.append(
                GraphAnalysisSignal(
                    scope=(
                        GraphSignalScope.PAIR
                    ),
                    signal_type=(
                        GraphSignalType
                        .DIRECT_RELATIONSHIP
                    ),
                    value=(
                        direct_edge
                        .final_strength
                    ),
                    normalized_value=(
                        direct_edge
                        .final_strength
                    ),
                    reason=(
                        "A direct structural "
                        "relationship exists between "
                        "the Entities."
                    ),
                    subject_entity_id=(
                        source_entity_id
                    ),
                    related_entity_id=(
                        target_entity_id
                    ),
                    metadata=(
                        (
                            "source_edge_count",
                            str(
                                direct_edge
                                .source_edge_count
                            ),
                        ),
                        (
                            "relationship_types",
                            ",".join(
                                direct_edge
                                .relationship_types
                            ),
                        ),
                        (
                            "confidence_strength",
                            self._format_float(
                                direct_edge
                                .confidence_strength
                            ),
                        ),
                    ),
                )
            )

            reasons.append(
                "Direct structural edge strength: "
                f"{self._format_float(direct_edge.final_strength)}."
            )

        # ======================================================
        # Component
        # ======================================================

        if same_component:

            component_signal_type = (
                GraphSignalType
                .SAME_COMPONENT
            )

            component_reason = (
                "Both Entities belong to the same "
                f"{result.components.mode.value} "
                "graph component."
            )

        else:

            component_signal_type = (
                GraphSignalType
                .DIFFERENT_COMPONENT
            )

            component_reason = (
                "The Entities belong to different "
                f"{result.components.mode.value} "
                "graph components."
            )

        signals.append(
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.PAIR
                ),
                signal_type=(
                    component_signal_type
                ),
                value=(
                    1.0
                    if same_component
                    else 0.0
                ),
                normalized_value=(
                    1.0
                    if same_component
                    else 0.0
                ),
                reason=(
                    component_reason
                ),
                subject_entity_id=(
                    source_entity_id
                ),
                related_entity_id=(
                    target_entity_id
                ),
                metadata=(
                    (
                        "component_mode",
                        result.components
                        .mode
                        .value,
                    ),
                ),
            )
        )

        reasons.append(
            component_reason
        )

        # ======================================================
        # Community
        # ======================================================

        if same_community:

            community_signal_type = (
                GraphSignalType
                .SAME_COMMUNITY
            )

            community_reason = (
                "Both Entities belong to the same "
                "Louvain community."
            )

        else:

            community_signal_type = (
                GraphSignalType
                .DIFFERENT_COMMUNITY
            )

            community_reason = (
                "The Entities belong to different "
                "Louvain communities."
            )

        signals.append(
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.PAIR
                ),
                signal_type=(
                    community_signal_type
                ),
                value=(
                    1.0
                    if same_community
                    else 0.0
                ),
                normalized_value=(
                    1.0
                    if same_community
                    else 0.0
                ),
                reason=(
                    community_reason
                ),
                subject_entity_id=(
                    source_entity_id
                ),
                related_entity_id=(
                    target_entity_id
                ),
            )
        )

        reasons.append(
            community_reason
        )

        # ======================================================
        # Missing-link prediction
        # ======================================================

        if prediction is not None:

            signals.extend(
                (
                    GraphAnalysisSignal(
                        scope=(
                            GraphSignalScope.PAIR
                        ),
                        signal_type=(
                            GraphSignalType
                            .COMMON_NEIGHBORS
                        ),
                        value=float(
                            prediction
                            .common_neighbors
                        ),
                        normalized_value=None,
                        reason=(
                            "The pair has structural "
                            "common neighbors."
                        ),
                        subject_entity_id=(
                            source_entity_id
                        ),
                        related_entity_id=(
                            target_entity_id
                        ),
                        metadata=(
                            (
                                "common_neighbor_ids",
                                ",".join(
                                    str(
                                        entity_id
                                    )
                                    for entity_id
                                    in prediction
                                    .common_neighbor_ids
                                ),
                            ),
                        ),
                    ),
                    GraphAnalysisSignal(
                        scope=(
                            GraphSignalScope.PAIR
                        ),
                        signal_type=(
                            GraphSignalType.JACCARD
                        ),
                        value=(
                            prediction.jaccard
                        ),
                        normalized_value=(
                            prediction.jaccard
                        ),
                        reason=(
                            "Jaccard neighborhood "
                            "overlap for the potential "
                            "missing link."
                        ),
                        subject_entity_id=(
                            source_entity_id
                        ),
                        related_entity_id=(
                            target_entity_id
                        ),
                    ),
                    GraphAnalysisSignal(
                        scope=(
                            GraphSignalScope.PAIR
                        ),
                        signal_type=(
                            GraphSignalType
                            .ADAMIC_ADAR
                        ),
                        value=(
                            prediction
                            .adamic_adar
                        ),
                        normalized_value=None,
                        reason=(
                            "Adamic-Adar structural "
                            "link-prediction score."
                        ),
                        subject_entity_id=(
                            source_entity_id
                        ),
                        related_entity_id=(
                            target_entity_id
                        ),
                    ),
                )
            )

            reasons.append(
                "Missing-link prediction: "
                f"{prediction.common_neighbors} common neighbor(s), "
                f"Jaccard {self._format_float(prediction.jaccard)}, "
                f"Adamic-Adar "
                f"{self._format_float(prediction.adamic_adar)}."
            )

        return GraphPairExplanation(
            source_entity_id=(
                source_entity_id
            ),
            target_entity_id=(
                target_entity_id
            ),
            direct_edge=direct_edge,
            prediction=prediction,
            same_component=(
                same_component
            ),
            component_mode=(
                result.components
                .mode
                .value
            ),
            same_community=(
                same_community
            ),
            signals=tuple(
                signals
            ),
            reasons=tuple(
                reasons
            ),
        )

    # ==========================================================
    # Graph signals
    # ==========================================================

    def _build_graph_signals(
        self,
        result: UnifiedGraphAnalysisResult,
    ) -> tuple[
        GraphAnalysisSignal,
        ...,
    ]:

        statistics = (
            result.statistics
        )

        signals = (
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType.DENSITY
                ),
                value=(
                    statistics.density
                ),
                normalized_value=(
                    statistics.density
                ),
                reason=(
                    "Simple structural graph density."
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType
                    .COMPONENT_COUNT
                ),
                value=float(
                    statistics
                    .component_count
                ),
                normalized_value=None,
                reason=(
                    "Number of structural graph "
                    "components."
                ),
                metadata=(
                    (
                        "component_mode",
                        result.components
                        .mode
                        .value,
                    ),
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType
                    .COMMUNITY_COUNT
                ),
                value=float(
                    statistics
                    .community_count
                ),
                normalized_value=None,
                reason=(
                    "Number of Louvain communities."
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType.MODULARITY
                ),
                value=(
                    result.communities
                    .modularity
                ),
                normalized_value=None,
                reason=(
                    "Louvain partition modularity."
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType
                    .LINK_PREDICTION_COUNT
                ),
                value=float(
                    statistics
                    .prediction_count
                ),
                normalized_value=None,
                reason=(
                    "Number of structural missing-link "
                    "predictions."
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.GRAPH
                ),
                signal_type=(
                    GraphSignalType
                    .STRUCTURAL_PAIR_COUNT
                ),
                value=float(
                    statistics
                    .structural_pair_count
                ),
                normalized_value=None,
                reason=(
                    "Number of direct structural "
                    "Entity pairs after edge-strength "
                    "aggregation."
                ),
            ),
        )

        return signals

    # ==========================================================
    # Entity explanation
    # ==========================================================

    def _explain_entity(
        self,
        result: UnifiedGraphAnalysisResult,
        entity: GraphEntityAnalysisResult,
        *,
        rank_maps: dict[
            str,
            dict[
                UUID,
                int,
            ],
        ],
    ) -> GraphEntityExplanation:

        entity_id = (
            entity.entity_id
        )

        component = (
            result.components
            .get_component(
                entity_id
            )
        )

        community = (
            result.communities
            .get_community(
                entity_id
            )
        )

        total_entities = (
            result.statistics
            .node_count
        )

        metric_ranks = (
            GraphMetricRank(
                metric=(
                    "degree"
                ),
                value=(
                    entity
                    .normalized_degree
                ),
                rank=(
                    rank_maps[
                        "degree"
                    ][
                        entity_id
                    ]
                ),
                total_entities=(
                    total_entities
                ),
            ),
            GraphMetricRank(
                metric=(
                    "pagerank"
                ),
                value=(
                    entity
                    .pagerank_score
                ),
                rank=(
                    rank_maps[
                        "pagerank"
                    ][
                        entity_id
                    ]
                ),
                total_entities=(
                    total_entities
                ),
            ),
            GraphMetricRank(
                metric=(
                    "betweenness"
                ),
                value=(
                    entity
                    .betweenness_score
                ),
                rank=(
                    rank_maps[
                        "betweenness"
                    ][
                        entity_id
                    ]
                ),
                total_entities=(
                    total_entities
                ),
            ),
        )

        signals: list[
            GraphAnalysisSignal
        ] = [
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.ENTITY
                ),
                signal_type=(
                    GraphSignalType
                    .DEGREE_CENTRALITY
                ),
                value=(
                    entity
                    .normalized_degree
                ),
                normalized_value=(
                    entity
                    .normalized_degree
                ),
                reason=(
                    "Normalized unique-neighbor "
                    "degree centrality."
                ),
                subject_entity_id=(
                    entity_id
                ),
                metadata=(
                    (
                        "raw_degree",
                        str(
                            entity
                            .degree
                            .degree
                        ),
                    ),
                    (
                        "unique_degree",
                        str(
                            entity
                            .degree
                            .unique_degree
                        ),
                    ),
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.ENTITY
                ),
                signal_type=(
                    GraphSignalType
                    .PAGERANK
                ),
                value=(
                    entity
                    .pagerank_score
                ),
                normalized_value=(
                    entity
                    .pagerank_score
                ),
                reason=(
                    "PageRank global graph "
                    "importance."
                ),
                subject_entity_id=(
                    entity_id
                ),
            ),
            GraphAnalysisSignal(
                scope=(
                    GraphSignalScope.ENTITY
                ),
                signal_type=(
                    GraphSignalType
                    .BETWEENNESS_CENTRALITY
                ),
                value=(
                    entity
                    .betweenness_score
                ),
                normalized_value=(
                    entity
                    .betweenness_score
                ),
                reason=(
                    "Normalized Brandes "
                    "betweenness centrality."
                ),
                subject_entity_id=(
                    entity_id
                ),
                metadata=(
                    (
                        "raw_betweenness",
                        self._format_float(
                            entity
                            .betweenness
                            .raw_score
                        ),
                    ),
                ),
            ),
        ]

        if (
            entity.betweenness
            .raw_score
            >
            0.0
        ):

            signals.append(
                GraphAnalysisSignal(
                    scope=(
                        GraphSignalScope.ENTITY
                    ),
                    signal_type=(
                        GraphSignalType
                        .BRIDGE_ROLE
                    ),
                    value=(
                        entity
                        .betweenness_score
                    ),
                    normalized_value=(
                        entity
                        .betweenness_score
                    ),
                    reason=(
                        "The Entity lies on at least "
                        "one shortest path between "
                        "other Entities."
                    ),
                    subject_entity_id=(
                        entity_id
                    ),
                )
            )

        if entity.is_isolated:

            signals.append(
                GraphAnalysisSignal(
                    scope=(
                        GraphSignalScope.ENTITY
                    ),
                    signal_type=(
                        GraphSignalType
                        .ISOLATED_ENTITY
                    ),
                    value=1.0,
                    normalized_value=1.0,
                    reason=(
                        "The Entity has no accepted "
                        "structural graph connections."
                    ),
                    subject_entity_id=(
                        entity_id
                    ),
                )
            )

        reasons = [
            (
                "Degree centrality "
                f"{self._format_float(entity.normalized_degree)} "
                f"(rank "
                f"{rank_maps['degree'][entity_id]}/"
                f"{total_entities})."
            ),
            (
                "PageRank "
                f"{self._format_float(entity.pagerank_score)} "
                f"(rank "
                f"{rank_maps['pagerank'][entity_id]}/"
                f"{total_entities})."
            ),
            (
                "Betweenness "
                f"{self._format_float(entity.betweenness_score)} "
                f"(rank "
                f"{rank_maps['betweenness'][entity_id]}/"
                f"{total_entities})."
            ),
            (
                f"Component {entity.component_index} "
                f"contains {component.size} Entity/Entities "
                f"using {result.components.mode.value} connectivity."
            ),
            (
                f"Louvain community {entity.community_id} "
                f"contains {community.size} Entity/Entities."
            ),
        ]

        if (
            entity.betweenness
            .raw_score
            >
            0.0
        ):

            reasons.append(
                "The Entity has a structural bridge role "
                "because its Brandes betweenness is positive."
            )

        if entity.is_isolated:

            reasons.append(
                "The Entity is structurally isolated."
            )

        return GraphEntityExplanation(
            entity_id=(
                entity_id
            ),
            component_index=(
                entity.component_index
            ),
            component_size=(
                component.size
            ),
            community_id=(
                entity.community_id
            ),
            community_size=(
                community.size
            ),
            metric_ranks=(
                metric_ranks
            ),
            signals=tuple(
                signals
            ),
            reasons=tuple(
                reasons
            ),
        )

    # ==========================================================
    # Rank maps
    # ==========================================================

    @staticmethod
    def _build_rank_maps(
        result: UnifiedGraphAnalysisResult,
    ) -> dict[
        str,
        dict[
            UUID,
            int,
        ],
    ]:

        total = len(
            result.entities
        )

        if total == 0:

            return {
                "degree": {},
                "pagerank": {},
                "betweenness": {},
            }

        degree_order = (
            result.top_by_degree(
                total
            )
        )

        pagerank_order = (
            result.top_by_pagerank(
                total
            )
        )

        betweenness_order = (
            result.top_by_betweenness(
                total
            )
        )

        return {
            "degree": {
                entity.entity_id: rank
                for rank, entity
                in enumerate(
                    degree_order,
                    start=1,
                )
            },
            "pagerank": {
                entity.entity_id: rank
                for rank, entity
                in enumerate(
                    pagerank_order,
                    start=1,
                )
            },
            "betweenness": {
                entity.entity_id: rank
                for rank, entity
                in enumerate(
                    betweenness_order,
                    start=1,
                )
            },
        }

    # ==========================================================
    # Direct edge lookup
    # ==========================================================

    @staticmethod
    def _find_direct_edge(
        result: UnifiedGraphAnalysisResult,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> (
        RelationshipEdgeStrength
        | None
    ):

        try:

            return (
                result.edge_weights
                .get(
                    source_entity_id,
                    target_entity_id,
                )
            )

        except KeyError:

            return None

    # ==========================================================
    # Prediction lookup
    # ==========================================================

    @staticmethod
    def _find_prediction(
        result: UnifiedGraphAnalysisResult,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> (
        LinkPredictionCandidate
        | None
    ):

        try:

            return (
                result.link_prediction
                .get(
                    source_entity_id,
                    target_entity_id,
                )
            )

        except KeyError:

            return None

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_result(
        result: UnifiedGraphAnalysisResult,
    ) -> None:

        if not isinstance(
            result,
            UnifiedGraphAnalysisResult,
        ):

            raise TypeError(
                "result must be "
                "UnifiedGraphAnalysisResult."
            )

    # ==========================================================
    # Formatting
    # ==========================================================

    @staticmethod
    def _format_float(
        value: float,
    ) -> str:

        value = float(
            value
        )

        if not isfinite(
            value
        ):

            raise ValueError(
                "Cannot format non-finite "
                "graph value."
            )

        return (
            f"{value:.6f}"
            .rstrip(
                "0"
            )
            .rstrip(
                "."
            )
            or
            "0"
        )