"""
Unified graph analysis.

Orchestrates all completed graph-analysis modules and
returns one structured result.

Pipeline:

EntityGraph
    ↓
Graph Normalization
    ↓
Degree Centrality
PageRank
Betweenness Centrality
Connected Components
Louvain Communities
Link Prediction
Relationship Edge Strength
    ↓
UnifiedGraphAnalysisResult

Responsibilities:

- provide one graph-analysis entry point
- reuse the common normalized graph
- preserve every analytical metric separately
- build per-Entity analytical views
- expose graph-level statistics
- validate cross-module consistency
- remain deterministic
- perform no database writes

Does NOT:

- query the database
- modify Entity or Relationship objects
- combine unrelated metrics into one score
- generate explanations
- generate Entity Resolution graph signals
- persist analysis results
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from math import isfinite

from uuid import UUID

from app.analysis.betweenness_centrality import (
    BetweennessCentralityNodeResult,
    BetweennessCentralityResult,
    BetweennessCentralityService,
)

from app.analysis.community_detection import (
    LouvainCommunityDetectionService,
    LouvainConfig,
    LouvainResult,
)

from app.analysis.connected_components import (
    ConnectedComponentMode,
    ConnectedComponentsResult,
    ConnectedComponentsService,
)

from app.analysis.degree_centrality import (
    DegreeCentralityNodeResult,
    DegreeCentralityResult,
    DegreeCentralityService,
)

from app.analysis.graph_contracts import (
    GraphSemantics,
)

from app.analysis.graph_normalization import (
    GraphNormalizationDiagnostics,
    GraphNormalizationService,
    NormalizedEntityGraph,
)

from app.analysis.link_prediction import (
    LinkPredictionConfig,
    LinkPredictionResult,
    LinkPredictionService,
)

from app.analysis.pagerank import (
    PageRankConfig,
    PageRankNodeResult,
    PageRankResult,
    PageRankService,
)

from app.analysis.relationship_edge_weight import (
    RelationshipEdgeWeightConfig,
    RelationshipEdgeWeightResult,
    RelationshipEdgeWeightService,
)

from app.models.entity_graph import (
    EntityGraph,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedGraphAnalysisConfig:
    """
    Complete configuration for one graph-analysis run.

    Every nested configuration belongs to the
    corresponding analytical module.

    No hidden score mixing or implicit weighting is
    performed here.
    """

    semantics: GraphSemantics = field(
        default_factory=GraphSemantics
    )

    pagerank: PageRankConfig = field(
        default_factory=PageRankConfig
    )

    louvain: LouvainConfig = field(
        default_factory=LouvainConfig
    )

    link_prediction: LinkPredictionConfig = field(
        default_factory=LinkPredictionConfig
    )

    edge_weight: (
        RelationshipEdgeWeightConfig
    ) = field(
        default_factory=(
            RelationshipEdgeWeightConfig
        )
    )

    component_mode: (
        ConnectedComponentMode
        | None
    ) = None

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
            self.pagerank,
            PageRankConfig,
        ):

            raise TypeError(
                "pagerank must be "
                "PageRankConfig."
            )

        if not isinstance(
            self.louvain,
            LouvainConfig,
        ):

            raise TypeError(
                "louvain must be "
                "LouvainConfig."
            )

        if not isinstance(
            self.link_prediction,
            LinkPredictionConfig,
        ):

            raise TypeError(
                "link_prediction must be "
                "LinkPredictionConfig."
            )

        if not isinstance(
            self.edge_weight,
            RelationshipEdgeWeightConfig,
        ):

            raise TypeError(
                "edge_weight must be "
                "RelationshipEdgeWeightConfig."
            )

        if (
            self.component_mode
            is not None
            and
            not isinstance(
                self.component_mode,
                ConnectedComponentMode,
            )
        ):

            raise TypeError(
                "component_mode must be "
                "ConnectedComponentMode or None."
            )


# ==========================================================
# Per-Entity unified result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class GraphEntityAnalysisResult:
    """
    Unified analytical view for one Entity.

    Metrics remain mathematically independent.

    No combined importance score is calculated here.
    """

    entity_id: UUID

    degree: DegreeCentralityNodeResult

    pagerank: PageRankNodeResult

    betweenness: (
        BetweennessCentralityNodeResult
    )

    component_index: int

    community_id: int

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

        if not isinstance(
            self.degree,
            DegreeCentralityNodeResult,
        ):

            raise TypeError(
                "degree must be "
                "DegreeCentralityNodeResult."
            )

        if not isinstance(
            self.pagerank,
            PageRankNodeResult,
        ):

            raise TypeError(
                "pagerank must be "
                "PageRankNodeResult."
            )

        if not isinstance(
            self.betweenness,
            BetweennessCentralityNodeResult,
        ):

            raise TypeError(
                "betweenness must be "
                "BetweennessCentralityNodeResult."
            )

        if (
            self.degree.entity_id
            !=
            self.entity_id
        ):

            raise ValueError(
                "Degree result Entity mismatch."
            )

        if (
            self.pagerank.entity_id
            !=
            self.entity_id
        ):

            raise ValueError(
                "PageRank result Entity mismatch."
            )

        if (
            self.betweenness.entity_id
            !=
            self.entity_id
        ):

            raise ValueError(
                "Betweenness result Entity mismatch."
            )

        if (
            not isinstance(
                self.component_index,
                int,
            )
            or self.component_index < 0
        ):

            raise ValueError(
                "component_index must be "
                "a non-negative integer."
            )

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

    # ==========================================================
    # Convenience properties
    # ==========================================================

    @property
    def normalized_degree(
        self,
    ) -> float:

        return (
            self.degree
            .normalized_degree
        )

    @property
    def pagerank_score(
        self,
    ) -> float:

        return (
            self.pagerank.score
        )

    @property
    def betweenness_score(
        self,
    ) -> float:

        return (
            self.betweenness
            .normalized_score
        )

    @property
    def is_isolated(
        self,
    ) -> bool:

        return (
            self.degree.is_isolated
        )

    @property
    def centrality_vector(
        self,
    ) -> dict[
        str,
        float,
    ]:
        """
        Return separate centrality dimensions.

        This is NOT a combined score.
        """

        return {
            "degree": (
                self.degree
                .normalized_degree
            ),
            "pagerank": (
                self.pagerank.score
            ),
            "betweenness": (
                self.betweenness
                .normalized_score
            ),
        }


# ==========================================================
# Graph-level statistics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedGraphStatistics:
    """
    High-level structural graph statistics.
    """

    node_count: int

    normalized_edge_count: int

    source_edge_count: int

    simple_edge_count: int

    density: float

    component_count: int

    community_count: int

    prediction_count: int

    isolated_entity_count: int

    structural_pair_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "node_count",
            "normalized_edge_count",
            "source_edge_count",
            "simple_edge_count",
            "component_count",
            "community_count",
            "prediction_count",
            "isolated_entity_count",
            "structural_pair_count",
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

        density = float(
            self.density
        )

        if (
            not isfinite(
                density
            )
            or not (
                0.0
                <= density
                <= 1.0
            )
        ):

            raise ValueError(
                "density must be between "
                "0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "density",
            density,
        )

        if (
            self.isolated_entity_count
            >
            self.node_count
        ):

            raise ValueError(
                "isolated_entity_count cannot "
                "exceed node_count."
            )


# ==========================================================
# Unified result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedGraphAnalysisResult:
    """
    Complete graph-analysis result.

    Every analytical subsystem remains accessible
    independently.

    This object is the canonical output of Phase 3.10.
    """

    semantics: GraphSemantics

    normalization: (
        GraphNormalizationDiagnostics
    )

    statistics: UnifiedGraphStatistics

    degree: DegreeCentralityResult

    pagerank: PageRankResult

    betweenness: (
        BetweennessCentralityResult
    )

    components: ConnectedComponentsResult

    communities: LouvainResult

    link_prediction: LinkPredictionResult

    edge_weights: (
        RelationshipEdgeWeightResult
    )

    entities: tuple[
        GraphEntityAnalysisResult,
        ...,
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
            self.normalization,
            GraphNormalizationDiagnostics,
        ):

            raise TypeError(
                "normalization must be "
                "GraphNormalizationDiagnostics."
            )

        if not isinstance(
            self.statistics,
            UnifiedGraphStatistics,
        ):

            raise TypeError(
                "statistics must be "
                "UnifiedGraphStatistics."
            )

        if not isinstance(
            self.degree,
            DegreeCentralityResult,
        ):

            raise TypeError(
                "degree must be "
                "DegreeCentralityResult."
            )

        if not isinstance(
            self.pagerank,
            PageRankResult,
        ):

            raise TypeError(
                "pagerank must be "
                "PageRankResult."
            )

        if not isinstance(
            self.betweenness,
            BetweennessCentralityResult,
        ):

            raise TypeError(
                "betweenness must be "
                "BetweennessCentralityResult."
            )

        if not isinstance(
            self.components,
            ConnectedComponentsResult,
        ):

            raise TypeError(
                "components must be "
                "ConnectedComponentsResult."
            )

        if not isinstance(
            self.communities,
            LouvainResult,
        ):

            raise TypeError(
                "communities must be "
                "LouvainResult."
            )

        if not isinstance(
            self.link_prediction,
            LinkPredictionResult,
        ):

            raise TypeError(
                "link_prediction must be "
                "LinkPredictionResult."
            )

        if not isinstance(
            self.edge_weights,
            RelationshipEdgeWeightResult,
        ):

            raise TypeError(
                "edge_weights must be "
                "RelationshipEdgeWeightResult."
            )

        if not isinstance(
            self.entities,
            tuple,
        ):

            raise TypeError(
                "entities must be a tuple."
            )

        seen: set[
            UUID
        ] = set()

        for entity in self.entities:

            if not isinstance(
                entity,
                GraphEntityAnalysisResult,
            ):

                raise TypeError(
                    "entities must contain "
                    "GraphEntityAnalysisResult."
                )

            if entity.entity_id in seen:

                raise ValueError(
                    "Duplicate unified Entity result."
                )

            seen.add(
                entity.entity_id
            )

        if (
            len(
                self.entities
            )
            !=
            self.statistics.node_count
        ):

            raise ValueError(
                "Unified Entity result count must "
                "match graph node count."
            )

        self._validate_cross_module_counts()

        self._validate_direction_consistency()

    # ==========================================================
    # Cross-module validation
    # ==========================================================

    def _validate_cross_module_counts(
        self,
    ) -> None:

        expected_nodes = (
            self.statistics.node_count
        )

        node_counts = (
            self.degree.node_count,
            self.pagerank.node_count,
            self.betweenness.node_count,
            self.components.node_count,
            self.communities.node_count,
            self.link_prediction.node_count,
        )

        for node_count in node_counts:

            if (
                node_count
                !=
                expected_nodes
            ):

                raise ValueError(
                    "Graph-analysis modules disagree "
                    "about node count."
                )

        expected_edges = (
            self.statistics
            .normalized_edge_count
        )

        edge_counts = (
            self.degree.edge_count,
            self.pagerank.edge_count,
            self.betweenness.edge_count,
            self.components.edge_count,
            self.communities.edge_count,
            self.link_prediction.edge_count,
            self.edge_weights
            .input_normalized_edge_count,
        )

        for edge_count in edge_counts:

            if (
                edge_count
                !=
                expected_edges
            ):

                raise ValueError(
                    "Graph-analysis modules disagree "
                    "about normalized edge count."
                )

    def _validate_direction_consistency(
        self,
    ) -> None:

        expected = (
            self.semantics.direction
        )

        directions = (
            self.degree.direction,
            self.betweenness.direction,
            self.components.direction,
            self.link_prediction.direction,
            self.edge_weights.direction,
            self.communities.source_direction,
        )

        for direction in directions:

            if direction != expected:

                raise ValueError(
                    "Graph-analysis modules disagree "
                    "about graph direction."
                )

    # ==========================================================
    # Entity access
    # ==========================================================

    def get_entity(
        self,
        entity_id: UUID,
    ) -> GraphEntityAnalysisResult:
        """
        Return unified analytical view for one Entity.
        """

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for entity in self.entities:

            if (
                entity.entity_id
                ==
                entity_id
            ):

                return entity

        raise KeyError(
            f"Unknown graph Entity: {entity_id}"
        )

    @property
    def entity_map(
        self,
    ) -> dict[
        UUID,
        GraphEntityAnalysisResult,
    ]:

        return {
            entity.entity_id: entity
            for entity
            in self.entities
        }

    # ==========================================================
    # Useful rankings
    # ==========================================================

    def top_by_degree(
        self,
        limit: int = 10,
    ) -> tuple[
        GraphEntityAnalysisResult,
        ...,
    ]:

        return self._top_entities(
            metric="degree",
            limit=limit,
        )

    def top_by_pagerank(
        self,
        limit: int = 10,
    ) -> tuple[
        GraphEntityAnalysisResult,
        ...,
    ]:

        return self._top_entities(
            metric="pagerank",
            limit=limit,
        )

    def top_by_betweenness(
        self,
        limit: int = 10,
    ) -> tuple[
        GraphEntityAnalysisResult,
        ...,
    ]:

        return self._top_entities(
            metric="betweenness",
            limit=limit,
        )

    def _top_entities(
        self,
        *,
        metric: str,
        limit: int,
    ) -> tuple[
        GraphEntityAnalysisResult,
        ...,
    ]:

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

        if metric == "degree":

            getter = (
                lambda item:
                item.normalized_degree
            )

        elif metric == "pagerank":

            getter = (
                lambda item:
                item.pagerank_score
            )

        elif metric == "betweenness":

            getter = (
                lambda item:
                item.betweenness_score
            )

        else:

            raise ValueError(
                "Unsupported unified graph metric."
            )

        ordered = sorted(
            self.entities,
            key=lambda item: (
                -float(
                    getter(
                        item
                    )
                ),
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


class UnifiedGraphAnalysisService:
    """
    Main entry point for complete graph analysis.

    All dependency arguments are optional to keep the
    service testable and integration-friendly.
    """

    def __init__(
        self,
        *,
        normalization_service: (
            GraphNormalizationService
            | None
        ) = None,
        degree_service: (
            DegreeCentralityService
            | None
        ) = None,
        pagerank_service: (
            PageRankService
            | None
        ) = None,
        betweenness_service: (
            BetweennessCentralityService
            | None
        ) = None,
        components_service: (
            ConnectedComponentsService
            | None
        ) = None,
        community_service: (
            LouvainCommunityDetectionService
            | None
        ) = None,
        link_prediction_service: (
            LinkPredictionService
            | None
        ) = None,
        edge_weight_service: (
            RelationshipEdgeWeightService
            | None
        ) = None,
    ) -> None:

        self.normalization_service = (
            normalization_service
            or GraphNormalizationService()
        )

        self.degree_service = (
            degree_service
            or DegreeCentralityService()
        )

        self.pagerank_service = (
            pagerank_service
            or PageRankService()
        )

        self.betweenness_service = (
            betweenness_service
            or BetweennessCentralityService()
        )

        self.components_service = (
            components_service
            or ConnectedComponentsService()
        )

        self.community_service = (
            community_service
            or LouvainCommunityDetectionService()
        )

        self.link_prediction_service = (
            link_prediction_service
            or LinkPredictionService()
        )

        self.edge_weight_service = (
            edge_weight_service
            or RelationshipEdgeWeightService()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        graph: EntityGraph,
        config: (
            UnifiedGraphAnalysisConfig
            | None
        ) = None,
    ) -> UnifiedGraphAnalysisResult:
        """
        Run complete graph analysis.

        No database writes are performed.
        """

        if not isinstance(
            graph,
            EntityGraph,
        ):

            raise TypeError(
                "graph must be EntityGraph."
            )

        config = (
            config
            or UnifiedGraphAnalysisConfig()
        )

        if not isinstance(
            config,
            UnifiedGraphAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "UnifiedGraphAnalysisConfig."
            )

        # ======================================================
        # Normalize exactly once.
        # ======================================================

        normalization_result = (
            self.normalization_service
            .normalize(
                graph,
                config.semantics,
            )
        )

        normalized_graph = (
            normalization_result.graph
        )

        # ======================================================
        # Independent analytical modules
        # ======================================================

        degree = (
            self.degree_service
            .analyze(
                normalized_graph
            )
        )

        pagerank = (
            self.pagerank_service
            .analyze(
                normalized_graph,
                config.pagerank,
            )
        )

        betweenness = (
            self.betweenness_service
            .analyze(
                normalized_graph
            )
        )

        components = (
            self.components_service
            .analyze(
                normalized_graph,
                config.component_mode,
            )
        )

        communities = (
            self.community_service
            .analyze(
                normalized_graph,
                config.louvain,
            )
        )

        link_prediction = (
            self.link_prediction_service
            .analyze(
                normalized_graph,
                config.link_prediction,
            )
        )

        edge_weights = (
            self.edge_weight_service
            .analyze(
                normalized_graph,
                config.edge_weight,
            )
        )

        # ======================================================
        # Unified per-Entity view
        # ======================================================

        entities = (
            self._build_entity_results(
                normalized_graph=(
                    normalized_graph
                ),
                degree=degree,
                pagerank=pagerank,
                betweenness=(
                    betweenness
                ),
                components=(
                    components
                ),
                communities=(
                    communities
                ),
            )
        )

        statistics = (
            self._build_statistics(
                normalized_graph=(
                    normalized_graph
                ),
                entities=entities,
                components=(
                    components
                ),
                communities=(
                    communities
                ),
                link_prediction=(
                    link_prediction
                ),
                edge_weights=(
                    edge_weights
                ),
            )
        )

        return (
            UnifiedGraphAnalysisResult(
                semantics=(
                    config.semantics
                ),
                normalization=(
                    normalization_result
                    .diagnostics
                ),
                statistics=(
                    statistics
                ),
                degree=degree,
                pagerank=pagerank,
                betweenness=(
                    betweenness
                ),
                components=(
                    components
                ),
                communities=(
                    communities
                ),
                link_prediction=(
                    link_prediction
                ),
                edge_weights=(
                    edge_weights
                ),
                entities=entities,
            )
        )

    # ==========================================================
    # Per-Entity aggregation
    # ==========================================================

    @staticmethod
    def _build_entity_results(
        *,
        normalized_graph: (
            NormalizedEntityGraph
        ),
        degree: DegreeCentralityResult,
        pagerank: PageRankResult,
        betweenness: (
            BetweennessCentralityResult
        ),
        components: (
            ConnectedComponentsResult
        ),
        communities: LouvainResult,
    ) -> tuple[
        GraphEntityAnalysisResult,
        ...,
    ]:

        component_index: dict[
            UUID,
            int,
        ] = {}

        for index, component in enumerate(
            components.components
        ):

            for entity_id in (
                component.entity_ids
            ):

                component_index[
                    entity_id
                ] = index

        community_index: dict[
            UUID,
            int,
        ] = {}

        for community in (
            communities.communities
        ):

            for entity_id in (
                community.entity_ids
            ):

                community_index[
                    entity_id
                ] = (
                    community.community_id
                )

        results: list[
            GraphEntityAnalysisResult
        ] = []

        for entity_id in sorted(
            normalized_graph.nodes,
            key=str,
        ):

            if (
                entity_id
                not in component_index
            ):

                raise ValueError(
                    "Entity missing from "
                    "component result."
                )

            if (
                entity_id
                not in community_index
            ):

                raise ValueError(
                    "Entity missing from "
                    "community result."
                )

            results.append(
                GraphEntityAnalysisResult(
                    entity_id=entity_id,
                    degree=(
                        degree.get(
                            entity_id
                        )
                    ),
                    pagerank=(
                        pagerank.get(
                            entity_id
                        )
                    ),
                    betweenness=(
                        betweenness.get(
                            entity_id
                        )
                    ),
                    component_index=(
                        component_index[
                            entity_id
                        ]
                    ),
                    community_id=(
                        community_index[
                            entity_id
                        ]
                    ),
                )
            )

        return tuple(
            results
        )

    # ==========================================================
    # Statistics
    # ==========================================================

    @staticmethod
    def _build_statistics(
        *,
        normalized_graph: (
            NormalizedEntityGraph
        ),
        entities: tuple[
            GraphEntityAnalysisResult,
            ...,
        ],
        components: (
            ConnectedComponentsResult
        ),
        communities: LouvainResult,
        link_prediction: (
            LinkPredictionResult
        ),
        edge_weights: (
            RelationshipEdgeWeightResult
        ),
    ) -> UnifiedGraphStatistics:

        isolated_entity_count = sum(
            1
            for entity
            in entities
            if entity.is_isolated
        )

        return (
            UnifiedGraphStatistics(
                node_count=(
                    normalized_graph
                    .node_count
                ),
                normalized_edge_count=(
                    normalized_graph
                    .edge_count
                ),
                source_edge_count=(
                    normalized_graph
                    .source_edge_count
                ),
                simple_edge_count=(
                    normalized_graph
                    .simple_edge_count
                ),
                density=(
                    normalized_graph
                    .density
                ),
                component_count=(
                    components
                    .component_count
                ),
                community_count=(
                    communities
                    .community_count
                ),
                prediction_count=(
                    link_prediction
                    .prediction_count
                ),
                isolated_entity_count=(
                    isolated_entity_count
                ),
                structural_pair_count=(
                    edge_weights
                    .structural_pair_count
                ),
            )
        )