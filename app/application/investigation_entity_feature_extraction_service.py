"""
Investigation Entity feature extraction.

Phase 5.5.

Transforms already completed investigation Graph + Temporal
analysis into one numerical feature matrix suitable for:

- Isolation Forest
- Local Outlier Factor
- DBSCAN

Pipeline:

InvestigationGraphAnalysisResult
        +
InvestigationTemporalAnalysisResult
        ↓
Entity-level quantitative feature extraction
        ↓
NumericFeatureMatrix
        ↓
Phase 5 anomaly / clustering algorithms

Feature vector:

Graph:
    graph_normalized_degree
    graph_pagerank
    graph_normalized_betweenness
    graph_component_size
    graph_community_size

Temporal:
    temporal_event_count
    temporal_active_window_count
    temporal_active_window_ratio
    temporal_burst_count
    temporal_change_point_count

Important semantic boundaries:

entity_id
    != numerical feature

component_index / community_id
    != numerical feature

missing temporal series
    != anomaly

isolated graph Entity
    != suspicious Entity

burst / change point
    != evidence

This service:

- does not query the database
- does not write to the database
- does not repeat Graph Analysis
- does not repeat Temporal Analysis
- does not run anomaly models
- does not create a combined intelligence score
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from uuid import UUID

from app.analysis.anomaly_contracts import (
    AnomalyObservation,
    NumericFeatureMatrix,
)

from app.analysis.graph_explainability import (
    GraphEntityExplanation,
)

from app.analysis.temporal_correlation import (
    TemporalActivitySeries,
    TemporalSeriesKind,
)

from app.analysis.unified_graph_analysis import (
    GraphEntityAnalysisResult,
)

from app.application.investigation_graph_analysis_service import (
    InvestigationGraphAnalysisResult,
)

from app.application.investigation_temporal_analysis_service import (
    InvestigationTemporalAnalysisResult,
)


# ==========================================================
# Canonical feature contract
# ==========================================================


INVESTIGATION_ENTITY_FEATURE_NAMES: tuple[
    str,
    ...,
] = (
    "graph_normalized_degree",
    "graph_pagerank",
    "graph_normalized_betweenness",
    "graph_component_size",
    "graph_community_size",
    "temporal_event_count",
    "temporal_active_window_count",
    "temporal_active_window_ratio",
    "temporal_burst_count",
    "temporal_change_point_count",
)


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityFeatureDiagnostics:
    """
    Coverage diagnostics for feature extraction.

    temporal_series_entity_count:

        Number of graph Entities for which an Entity-level
        temporal activity series exists.

    graph_entities_without_temporal_series:

        Graph Entities with no Entity-linked temporal
        activity series.

        Their temporal numerical features are represented
        as zero observed activity.

        This is NOT interpreted as anomaly.

    temporal_only_entity_ids:

        Entity temporal series that exist in the temporal
        result but do not correspond to a graph Entity.

        They are reported rather than silently converted
        into graph-less feature rows.
    """

    graph_entity_count: int

    temporal_series_entity_count: int

    graph_entities_without_temporal_series: tuple[
        str,
        ...,
    ]

    temporal_only_entity_ids: tuple[
        str,
        ...,
    ]

    feature_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "graph_entity_count",
            "temporal_series_entity_count",
            "feature_count",
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
                or isinstance(
                    value,
                    bool,
                )
                or value < 0
            ):

                raise ValueError(
                    f"{field_name} must be "
                    "a non-negative integer."
                )

        if not isinstance(
            self.graph_entities_without_temporal_series,
            tuple,
        ):

            raise TypeError(
                "graph_entities_without_temporal_series "
                "must be tuple."
            )

        if not isinstance(
            self.temporal_only_entity_ids,
            tuple,
        ):

            raise TypeError(
                "temporal_only_entity_ids must be tuple."
            )

        if (
            self.temporal_series_entity_count
            >
            self.graph_entity_count
        ):

            raise ValueError(
                "Temporal-series Entity count cannot "
                "exceed graph Entity count."
            )

        if (
            self.temporal_series_entity_count
            +
            len(
                self.graph_entities_without_temporal_series
            )
            !=
            self.graph_entity_count
        ):

            raise ValueError(
                "Temporal coverage diagnostics do not "
                "match graph Entity count."
            )

        if (
            self.feature_count
            !=
            len(
                INVESTIGATION_ENTITY_FEATURE_NAMES
            )
        ):

            raise ValueError(
                "Unexpected investigation Entity "
                "feature count."
            )

        if (
            tuple(
                sorted(
                    self.graph_entities_without_temporal_series
                )
            )
            !=
            self.graph_entities_without_temporal_series
        ):

            raise ValueError(
                "Missing temporal Entity IDs must "
                "be deterministically sorted."
            )

        if (
            tuple(
                sorted(
                    self.temporal_only_entity_ids
                )
            )
            !=
            self.temporal_only_entity_ids
        ):

            raise ValueError(
                "Temporal-only Entity IDs must "
                "be deterministically sorted."
            )


# ==========================================================
# Complete extraction result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityFeatureExtractionResult:
    """
    Complete production feature-extraction result.
    """

    case_id: UUID

    matrix: NumericFeatureMatrix

    diagnostics: (
        InvestigationEntityFeatureDiagnostics
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.matrix,
            NumericFeatureMatrix,
        ):

            raise TypeError(
                "matrix must be NumericFeatureMatrix."
            )

        if not isinstance(
            self.diagnostics,
            InvestigationEntityFeatureDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "InvestigationEntityFeatureDiagnostics."
            )

        if (
            self.matrix.feature_names
            !=
            INVESTIGATION_ENTITY_FEATURE_NAMES
        ):

            raise ValueError(
                "Unexpected Entity feature contract."
            )

        if (
            self.matrix.sample_count
            !=
            self.diagnostics.graph_entity_count
        ):

            raise ValueError(
                "Feature matrix sample count must "
                "equal graph Entity count."
            )

        if (
            self.matrix.feature_count
            !=
            self.diagnostics.feature_count
        ):

            raise ValueError(
                "Feature matrix / diagnostics "
                "feature count mismatch."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def entity_count(
        self,
    ) -> int:

        return (
            self.matrix.sample_count
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return (
            self.matrix.feature_count
        )

    @property
    def feature_names(
        self,
    ) -> tuple[
        str,
        ...,
    ]:

        return (
            self.matrix.feature_names
        )


# ==========================================================
# Service
# ==========================================================


class InvestigationEntityFeatureExtractionService:
    """
    Build the canonical Phase 5 Entity feature matrix from
    completed Phase 3 and Phase 4 investigation results.

    This is a translation/orchestration service.

    Graph and temporal mathematics are NOT repeated.
    """

    FEATURE_NAMES = (
        INVESTIGATION_ENTITY_FEATURE_NAMES
    )

    # ==========================================================
    # Complete extraction
    # ==========================================================

    def extract(
        self,
        graph_result: InvestigationGraphAnalysisResult,
        temporal_result: (
            InvestigationTemporalAnalysisResult
        ),
    ) -> InvestigationEntityFeatureExtractionResult:
        """
        Convert Graph + Temporal Entity analytics into one
        deterministic numerical matrix.
        """

        if not isinstance(
            graph_result,
            InvestigationGraphAnalysisResult,
        ):

            raise TypeError(
                "graph_result must be "
                "InvestigationGraphAnalysisResult."
            )

        if not isinstance(
            temporal_result,
            InvestigationTemporalAnalysisResult,
        ):

            raise TypeError(
                "temporal_result must be "
                "InvestigationTemporalAnalysisResult."
            )

        if (
            graph_result.case_id
            !=
            temporal_result.case_id
        ):

            raise ValueError(
                "Graph and Temporal results belong "
                "to different investigation cases."
            )

        case_id = (
            graph_result.case_id
        )

        # ======================================================
        # Graph Entity map
        # ======================================================

        graph_entities: dict[
            UUID,
            GraphEntityAnalysisResult,
        ] = {}

        for entity in (
            graph_result
            .analysis
            .entities
        ):

            if entity.entity_id in graph_entities:

                raise ValueError(
                    "Duplicate Entity in graph "
                    "analysis result."
                )

            graph_entities[
                entity.entity_id
            ] = entity

        # ======================================================
        # Temporal Entity-series map
        # ======================================================

        temporal_series: dict[
            UUID,
            TemporalActivitySeries,
        ] = {}

        for series in (
            temporal_result
            .analysis
            .correlation
            .entity_series
        ):

            if (
                series.kind
                !=
                TemporalSeriesKind.ENTITY
            ):

                raise ValueError(
                    "Entity temporal-series collection "
                    "contains non-Entity series."
                )

            entity_id = UUID(
                series.series_id
            )

            if entity_id in temporal_series:

                raise ValueError(
                    "Duplicate Entity temporal series."
                )

            temporal_series[
                entity_id
            ] = series

        # ======================================================
        # Canonical Entity order
        # ======================================================

        ordered_entity_ids = tuple(
            sorted(
                graph_entities,
                key=lambda entity_id: (
                    str(
                        entity_id
                    )
                ),
            )
        )

        graph_entity_id_set = set(
            ordered_entity_ids
        )

        temporal_entity_id_set = set(
            temporal_series
        )

        missing_temporal_ids = tuple(
            sorted(
                (
                    str(
                        entity_id
                    )
                    for entity_id
                    in (
                        graph_entity_id_set
                        -
                        temporal_entity_id_set
                    )
                )
            )
        )

        temporal_only_ids = tuple(
            sorted(
                (
                    str(
                        entity_id
                    )
                    for entity_id
                    in (
                        temporal_entity_id_set
                        -
                        graph_entity_id_set
                    )
                )
            )
        )

        # ======================================================
        # Build observations
        # ======================================================

        observations: list[
            AnomalyObservation
        ] = []

        for entity_id in ordered_entity_ids:

            graph_entity = (
                graph_entities[
                    entity_id
                ]
            )

            graph_explanation = (
                graph_result
                .explainability
                .get_entity(
                    entity_id
                )
            )

            entity_temporal_series = (
                temporal_series.get(
                    entity_id
                )
            )

            burst_count = len(
                temporal_result
                .analysis
                .bursts
                .bursts_for_entity(
                    entity_id
                )
            )

            change_point_count = len(
                temporal_result
                .analysis
                .change_points
                .changes_for_entity(
                    entity_id
                )
            )

            observations.append(
                self.build_entity_observation(
                    graph_entity=(
                        graph_entity
                    ),
                    graph_explanation=(
                        graph_explanation
                    ),
                    temporal_series=(
                        entity_temporal_series
                    ),
                    burst_count=(
                        burst_count
                    ),
                    change_point_count=(
                        change_point_count
                    ),
                )
            )

        # ======================================================
        # Matrix
        # ======================================================

        matrix = (
            NumericFeatureMatrix(
                feature_names=(
                    self.FEATURE_NAMES
                ),
                observations=tuple(
                    observations
                ),
            )
            .canonicalized()
        )

        # ======================================================
        # Diagnostics
        # ======================================================

        diagnostics = (
            InvestigationEntityFeatureDiagnostics(
                graph_entity_count=len(
                    graph_entities
                ),
                temporal_series_entity_count=len(
                    graph_entity_id_set
                    &
                    temporal_entity_id_set
                ),
                graph_entities_without_temporal_series=(
                    missing_temporal_ids
                ),
                temporal_only_entity_ids=(
                    temporal_only_ids
                ),
                feature_count=len(
                    self.FEATURE_NAMES
                ),
            )
        )

        return (
            InvestigationEntityFeatureExtractionResult(
                case_id=case_id,
                matrix=matrix,
                diagnostics=diagnostics,
            )
        )

    # ==========================================================
    # One Entity
    # ==========================================================

    def build_entity_observation(
        self,
        *,
        graph_entity: GraphEntityAnalysisResult,
        graph_explanation: GraphEntityExplanation,
        temporal_series: (
            TemporalActivitySeries
            | None
        ),
        burst_count: int,
        change_point_count: int,
    ) -> AnomalyObservation:
        """
        Build one canonical Entity numerical observation.

        Exposed separately so the feature contract can be
        regression-tested without database access.
        """

        if not isinstance(
            graph_entity,
            GraphEntityAnalysisResult,
        ):

            raise TypeError(
                "graph_entity must be "
                "GraphEntityAnalysisResult."
            )

        if not isinstance(
            graph_explanation,
            GraphEntityExplanation,
        ):

            raise TypeError(
                "graph_explanation must be "
                "GraphEntityExplanation."
            )

        entity_id = (
            graph_entity.entity_id
        )

        if (
            graph_explanation.entity_id
            !=
            entity_id
        ):

            raise ValueError(
                "Graph Entity and graph explanation "
                "belong to different Entities."
            )

        if (
            graph_explanation.component_index
            !=
            graph_entity.component_index
        ):

            raise ValueError(
                "Graph component mismatch."
            )

        if (
            graph_explanation.community_id
            !=
            graph_entity.community_id
        ):

            raise ValueError(
                "Graph community mismatch."
            )

        burst_count = (
            self._validate_count(
                burst_count,
                "burst_count",
            )
        )

        change_point_count = (
            self._validate_count(
                change_point_count,
                "change_point_count",
            )
        )

        # ======================================================
        # Temporal quantitative features
        # ======================================================

        if temporal_series is None:

            temporal_event_count = 0

            temporal_active_window_count = 0

            temporal_active_window_ratio = 0.0

        else:

            if not isinstance(
                temporal_series,
                TemporalActivitySeries,
            ):

                raise TypeError(
                    "temporal_series must be "
                    "TemporalActivitySeries or None."
                )

            if (
                temporal_series.kind
                !=
                TemporalSeriesKind.ENTITY
            ):

                raise ValueError(
                    "temporal_series must represent "
                    "an Entity."
                )

            if (
                UUID(
                    temporal_series.series_id
                )
                !=
                entity_id
            ):

                raise ValueError(
                    "Temporal series belongs to "
                    "another Entity."
                )

            temporal_event_count = sum(
                temporal_series.counts
            )

            temporal_active_window_count = sum(
                1
                for count
                in temporal_series.counts
                if count > 0
            )

            temporal_window_count = len(
                temporal_series.counts
            )

            if temporal_window_count > 0:

                temporal_active_window_ratio = (
                    temporal_active_window_count
                    /
                    temporal_window_count
                )

            else:

                temporal_active_window_ratio = 0.0

        # ======================================================
        # Canonical vector
        #
        # Deliberately excluded:
        #
        # entity_id
        # component_index
        # community_id
        # ======================================================

        values = (
            float(
                graph_entity
                .degree
                .normalized_degree
            ),
            float(
                graph_entity
                .pagerank
                .score
            ),
            float(
                graph_entity
                .betweenness
                .normalized_score
            ),
            float(
                graph_explanation
                .component_size
            ),
            float(
                graph_explanation
                .community_size
            ),
            float(
                temporal_event_count
            ),
            float(
                temporal_active_window_count
            ),
            float(
                temporal_active_window_ratio
            ),
            float(
                burst_count
            ),
            float(
                change_point_count
            ),
        )

        return (
            AnomalyObservation(
                observation_id=str(
                    entity_id
                ),
                values=values,
            )
        )

    # ==========================================================
    # Count validation
    # ==========================================================

    @staticmethod
    def _validate_count(
        value: int,
        name: str,
    ) -> int:

        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
        ):

            raise ValueError(
                f"{name} must be "
                "a non-negative integer."
            )

        return value