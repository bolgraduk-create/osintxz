"""
Investigation anomaly-analysis application service.

Phase 5.5.

Connects completed investigation analytics to the
Phase 5 anomaly / density-analysis pipeline.

Pipeline:

case_id
    ↓
InvestigationGraphAnalysisService
    ↓
InvestigationGraphAnalysisResult

case_id
    ↓
InvestigationTemporalAnalysisService
    ↓
InvestigationTemporalAnalysisResult

Graph + Temporal results
    ↓
InvestigationEntityFeatureExtractionService
    ↓
NumericFeatureMatrix

NumericFeatureMatrix
    ↓
UnifiedAnomalyAnalysisService
    ↓
UnifiedAnomalyAnalysisResult

    ↓
InvestigationAnomalyAnalysisResult


Responsibilities:

- preserve one investigation case scope
- execute Graph Analysis exactly once
- execute Temporal Analysis exactly once
- extract Entity features exactly once
- execute Unified Anomaly Analysis exactly once
- preserve all intermediate analytical results
- keep Phase 5 separate from persistence

Does NOT:

- create or modify Entities
- create or modify Relationships
- create or modify Evidence
- merge Entities
- create Entity Resolution signals
- persist anomaly-analysis results
- convert anomaly output into evidence
- convert anomaly output into identity confidence
- convert DBSCAN clusters into Relationships
- convert DBSCAN noise into anomaly proof
- create a combined intelligence score
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from uuid import UUID

from app.analysis.unified_anomaly_analysis import (
    UnifiedAnomalyAnalysisConfig,
    UnifiedAnomalyAnalysisResult,
    UnifiedAnomalyAnalysisService,
)

from app.analysis.unified_graph_analysis import (
    UnifiedGraphAnalysisConfig,
)

from app.analysis.unified_temporal_analysis import (
    UnifiedTemporalAnalysisConfig,
)

from app.application.investigation_entity_feature_extraction_service import (
    InvestigationEntityFeatureExtractionResult,
    InvestigationEntityFeatureExtractionService,
)

from app.application.investigation_graph_analysis_service import (
    InvestigationGraphAnalysisResult,
    InvestigationGraphAnalysisService,
)

from app.application.investigation_temporal_analysis_service import (
    InvestigationTemporalAnalysisResult,
    InvestigationTemporalAnalysisService,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnomalyAnalysisConfig:
    """
    Complete Phase 5 investigation configuration.

    Every analytical subsystem retains its own
    configuration and mathematical semantics.
    """

    graph: UnifiedGraphAnalysisConfig = field(
        default_factory=(
            UnifiedGraphAnalysisConfig
        )
    )

    temporal: UnifiedTemporalAnalysisConfig = field(
        default_factory=(
            UnifiedTemporalAnalysisConfig
        )
    )

    anomaly: UnifiedAnomalyAnalysisConfig = field(
        default_factory=(
            UnifiedAnomalyAnalysisConfig
        )
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.graph,
            UnifiedGraphAnalysisConfig,
        ):

            raise TypeError(
                "graph must be "
                "UnifiedGraphAnalysisConfig."
            )

        if not isinstance(
            self.temporal,
            UnifiedTemporalAnalysisConfig,
        ):

            raise TypeError(
                "temporal must be "
                "UnifiedTemporalAnalysisConfig."
            )

        if not isinstance(
            self.anomaly,
            UnifiedAnomalyAnalysisConfig,
        ):

            raise TypeError(
                "anomaly must be "
                "UnifiedAnomalyAnalysisConfig."
            )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnomalyAnalysisResult:
    """
    Complete Phase 5 result for one investigation case.

    All intermediate analytical results are retained so
    callers can inspect exactly where every numerical
    feature and model output came from.
    """

    case_id: UUID

    graph: InvestigationGraphAnalysisResult

    temporal: InvestigationTemporalAnalysisResult

    features: (
        InvestigationEntityFeatureExtractionResult
    )

    analysis: UnifiedAnomalyAnalysisResult

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # Types
        # ======================================================

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.graph,
            InvestigationGraphAnalysisResult,
        ):

            raise TypeError(
                "graph must be "
                "InvestigationGraphAnalysisResult."
            )

        if not isinstance(
            self.temporal,
            InvestigationTemporalAnalysisResult,
        ):

            raise TypeError(
                "temporal must be "
                "InvestigationTemporalAnalysisResult."
            )

        if not isinstance(
            self.features,
            InvestigationEntityFeatureExtractionResult,
        ):

            raise TypeError(
                "features must be "
                "InvestigationEntityFeatureExtractionResult."
            )

        if not isinstance(
            self.analysis,
            UnifiedAnomalyAnalysisResult,
        ):

            raise TypeError(
                "analysis must be "
                "UnifiedAnomalyAnalysisResult."
            )

        # ======================================================
        # Case scope
        # ======================================================

        if (
            self.graph.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Graph analysis belongs "
                "to another case."
            )

        if (
            self.temporal.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Temporal analysis belongs "
                "to another case."
            )

        if (
            self.features.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Feature extraction belongs "
                "to another case."
            )

        # ======================================================
        # Shared feature matrix
        # ======================================================

        if (
            self.analysis.matrix
            !=
            self.features.matrix
        ):

            raise ValueError(
                "Anomaly analysis matrix does not "
                "match extracted Entity features."
            )

        # ======================================================
        # Entity/sample count
        # ======================================================

        if (
            self.analysis.sample_count
            !=
            self.features.entity_count
        ):

            raise ValueError(
                "Anomaly sample count does not "
                "match Entity feature count."
            )

        if (
            self.analysis.feature_count
            !=
            self.features.feature_count
        ):

            raise ValueError(
                "Anomaly feature count does not "
                "match Entity feature contract."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def entity_count(
        self,
    ) -> int:

        return (
            self.features.entity_count
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return (
            self.features.feature_count
        )

    @property
    def isolation_forest_outlier_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .isolation_forest_outlier_count
        )

    @property
    def local_outlier_factor_outlier_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .local_outlier_factor_outlier_count
        )

    @property
    def dual_outlier_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .dual_outlier_count
        )

    @property
    def dbscan_cluster_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .dbscan_cluster_count
        )

    @property
    def dbscan_noise_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .dbscan_noise_count
        )

    @property
    def graph_entities_without_temporal_series_count(
        self,
    ) -> int:

        return len(
            self.features
            .diagnostics
            .graph_entities_without_temporal_series
        )

    @property
    def temporal_only_entity_count(
        self,
    ) -> int:

        return len(
            self.features
            .diagnostics
            .temporal_only_entity_ids
        )

    # ==========================================================
    # Entity lookup
    # ==========================================================

    def get_entity(
        self,
        entity_id: str | UUID,
    ):
        """
        Return the unified Phase 5 result for one Entity.

        The observation ID contract is the canonical UUID
        string used by the feature matrix.
        """

        if isinstance(
            entity_id,
            UUID,
        ):

            target = str(
                entity_id
            )

        else:

            try:

                target = str(
                    UUID(
                        str(
                            entity_id
                        )
                    )
                )

            except (
                TypeError,
                ValueError,
                AttributeError,
            ) as error:

                raise ValueError(
                    "Invalid Entity ID."
                ) from error

        return (
            self.analysis
            .get_observation(
                target
            )
        )


# ==========================================================
# Application service
# ==========================================================


class InvestigationAnomalyAnalysisService:
    """
    Application-level Phase 5 orchestration.

    Existing Phase 3 and Phase 4 application services own
    their respective analytical pipelines.

    This service only composes them with:

    - Entity feature extraction
    - Unified anomaly analysis
    """

    def __init__(
        self,
        investigation_graph_analysis_service: (
            InvestigationGraphAnalysisService
        ),
        investigation_temporal_analysis_service: (
            InvestigationTemporalAnalysisService
        ),
        entity_feature_extraction_service: (
            InvestigationEntityFeatureExtractionService
            | None
        ) = None,
        unified_anomaly_analysis_service: (
            UnifiedAnomalyAnalysisService
            | None
        ) = None,
    ) -> None:

        if not isinstance(
            investigation_graph_analysis_service,
            InvestigationGraphAnalysisService,
        ):

            raise TypeError(
                "investigation_graph_analysis_service "
                "must be "
                "InvestigationGraphAnalysisService."
            )

        if not isinstance(
            investigation_temporal_analysis_service,
            InvestigationTemporalAnalysisService,
        ):

            raise TypeError(
                "investigation_temporal_analysis_service "
                "must be "
                "InvestigationTemporalAnalysisService."
            )

        if (
            entity_feature_extraction_service
            is not None
            and
            not isinstance(
                entity_feature_extraction_service,
                InvestigationEntityFeatureExtractionService,
            )
        ):

            raise TypeError(
                "entity_feature_extraction_service "
                "must be "
                "InvestigationEntityFeatureExtractionService."
            )

        if (
            unified_anomaly_analysis_service
            is not None
            and
            not isinstance(
                unified_anomaly_analysis_service,
                UnifiedAnomalyAnalysisService,
            )
        ):

            raise TypeError(
                "unified_anomaly_analysis_service "
                "must be "
                "UnifiedAnomalyAnalysisService."
            )

        self.investigation_graph_analysis_service = (
            investigation_graph_analysis_service
        )

        self.investigation_temporal_analysis_service = (
            investigation_temporal_analysis_service
        )

        self.entity_feature_extraction_service = (
            entity_feature_extraction_service
            or
            InvestigationEntityFeatureExtractionService()
        )

        self.unified_anomaly_analysis_service = (
            unified_anomaly_analysis_service
            or
            UnifiedAnomalyAnalysisService()
        )

    # ==========================================================
    # Complete Phase 5 analysis
    # ==========================================================

    def analyze_case(
        self,
        case_id: str | UUID,
        config: (
            InvestigationAnomalyAnalysisConfig
            | None
        ) = None,
    ) -> InvestigationAnomalyAnalysisResult:
        """
        Execute complete anomaly analysis for one case.

        This compatibility entry point computes Graph and Temporal
        itself, then delegates to analyze_precomputed().

        InvestigationAnalysisOrchestrator should use
        analyze_precomputed() so already calculated Graph and
        Temporal results are reused instead of recomputed.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        config = (
            config
            or
            InvestigationAnomalyAnalysisConfig()
        )

        if not isinstance(
            config,
            InvestigationAnomalyAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "InvestigationAnomalyAnalysisConfig."
            )

        graph_result = (
            self.investigation_graph_analysis_service
            .analyze_case(
                case_uuid,
                config.graph,
            )
        )

        temporal_result = (
            self.investigation_temporal_analysis_service
            .analyze_case(
                case_uuid,
                config.temporal,
            )
        )

        return self.analyze_precomputed(
            case_id=case_uuid,
            graph_result=graph_result,
            temporal_result=temporal_result,
            config=config,
        )

    def analyze_precomputed(
        self,
        *,
        case_id: str | UUID,
        graph_result: InvestigationGraphAnalysisResult,
        temporal_result: InvestigationTemporalAnalysisResult,
        feature_result: (
            InvestigationEntityFeatureExtractionResult
            | None
        ) = None,
        config: (
            InvestigationAnomalyAnalysisConfig
            | None
        ) = None,
    ) -> InvestigationAnomalyAnalysisResult:
        """
        Analyze anomalies using already calculated Graph and
        Temporal results.

        feature_result may also be supplied when the shared Entity
        feature matrix has already been calculated.

        No Graph or Temporal analysis is executed by this method.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        config = (
            config
            or
            InvestigationAnomalyAnalysisConfig()
        )

        if not isinstance(
            config,
            InvestigationAnomalyAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "InvestigationAnomalyAnalysisConfig."
            )

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

        if feature_result is None:

            feature_result = (
                self.entity_feature_extraction_service
                .extract(
                    graph_result,
                    temporal_result,
                )
            )

        if not isinstance(
            feature_result,
            InvestigationEntityFeatureExtractionResult,
        ):

            raise TypeError(
                "feature_result must be "
                "InvestigationEntityFeatureExtractionResult."
            )

        anomaly_result = (
            self.unified_anomaly_analysis_service
            .analyze(
                feature_result.matrix,
                config.anomaly,
            )
        )

        return (
            InvestigationAnomalyAnalysisResult(
                case_id=case_uuid,
                graph=graph_result,
                temporal=temporal_result,
                features=feature_result,
                analysis=anomaly_result,
            )
        )

    # ==========================================================
    # Case identifier
    # ==========================================================

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:

        if isinstance(
            case_id,
            UUID,
        ):

            return case_id

        try:

            return UUID(
                str(
                    case_id
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                "Invalid investigation case ID."
            ) from error