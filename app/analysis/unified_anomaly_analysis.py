"""
Unified anomaly and density analysis.

Phase 5.4.

Combines:

- Isolation Forest
- Local Outlier Factor
- DBSCAN

over one shared NumericFeatureMatrix.

Pipeline:

NumericFeatureMatrix
    ↓
    ├──────────────────────────────┐
    ↓                              ↓
Isolation Forest              Local Outlier Factor
    ↓                              ↓
global isolation signal       local density signal
    │                              │
    └──────────────┬───────────────┘
                   │
                   ├─────────────── DBSCAN
                   │                density structure
                   ↓
        UnifiedAnomalyAnalysisResult

Important:

Raw model scores are NOT combined.

Isolation Forest anomaly_score
    != LOF local_outlier_factor

DBSCAN noise
    != anomaly score
    != automatic outlier signal

The unified layer only aligns results by observation_id
and exposes independent model outputs.

The optional outlier_method_count:

    0, 1, or 2

counts binary outlier classifications from:

- Isolation Forest
- Local Outlier Factor

It is NOT:

- probability
- confidence
- evidence strength
- risk score
- suspiciousness score

DBSCAN noise is deliberately excluded from that count.

Does NOT:

- query the database
- write to the database
- create Evidence
- create Relationships
- merge Entities
- infer identity
- infer maliciousness
- infer criminality
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from app.analysis.anomaly_contracts import (
    NumericFeatureMatrix,
)

from app.analysis.dbscan_clustering import (
    DBSCANClusteringResult,
    DBSCANClusteringService,
    DBSCANConfig,
    DBSCANObservationResult,
    DBSCANStatus,
)

from app.analysis.isolation_forest_anomaly import (
    IsolationForestAnomalyService,
    IsolationForestConfig,
    IsolationForestObservationResult,
    IsolationForestResult,
    IsolationForestStatus,
)

from app.analysis.local_outlier_factor_anomaly import (
    LocalOutlierFactorAnomalyService,
    LocalOutlierFactorConfig,
    LocalOutlierFactorObservationResult,
    LocalOutlierFactorResult,
    LocalOutlierFactorStatus,
)


# ==========================================================
# Unified execution status
# ==========================================================


class UnifiedAnomalyStatus(
    str,
    Enum,
):
    """
    Execution status of the complete Phase 5 analytical
    layer.

    COMPLETE:
        All three algorithms executed successfully.

    PARTIAL:
        At least one algorithm executed successfully,
        but not all three.

    UNAVAILABLE:
        Input exists, but none of the algorithms could
        be fitted.

    EMPTY:
        Input matrix contains zero observations.
    """

    COMPLETE = "complete"

    PARTIAL = "partial"

    UNAVAILABLE = "unavailable"

    EMPTY = "empty"


# ==========================================================
# Unified configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedAnomalyAnalysisConfig:
    """
    Configuration of all Phase 5 algorithms.

    Each algorithm retains independent configuration and
    mathematical semantics.
    """

    isolation_forest: IsolationForestConfig = field(
        default_factory=(
            IsolationForestConfig
        )
    )

    local_outlier_factor: (
        LocalOutlierFactorConfig
    ) = field(
        default_factory=(
            LocalOutlierFactorConfig
        )
    )

    dbscan: DBSCANConfig = field(
        default_factory=(
            DBSCANConfig
        )
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.isolation_forest,
            IsolationForestConfig,
        ):

            raise TypeError(
                "isolation_forest must be "
                "IsolationForestConfig."
            )

        if not isinstance(
            self.local_outlier_factor,
            LocalOutlierFactorConfig,
        ):

            raise TypeError(
                "local_outlier_factor must be "
                "LocalOutlierFactorConfig."
            )

        if not isinstance(
            self.dbscan,
            DBSCANConfig,
        ):

            raise TypeError(
                "dbscan must be DBSCANConfig."
            )


# ==========================================================
# Unified observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedAnomalyObservationResult:
    """
    Cross-module view of one numerical observation.

    Algorithm results are optional because an individual
    model may be unavailable due to:

    - insufficient samples
    - no numerical variation
    - empty input

    No model score is normalized or averaged here.
    """

    observation_id: str

    isolation_forest: (
        IsolationForestObservationResult
        | None
    )

    local_outlier_factor: (
        LocalOutlierFactorObservationResult
        | None
    )

    dbscan: (
        DBSCANObservationResult
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.observation_id,
                str,
            )
            or not self.observation_id.strip()
        ):

            raise ValueError(
                "observation_id cannot be empty."
            )

        normalized_id = (
            self.observation_id.strip()
        )

        object.__setattr__(
            self,
            "observation_id",
            normalized_id,
        )

        if (
            self.isolation_forest
            is not None
        ):

            if not isinstance(
                self.isolation_forest,
                IsolationForestObservationResult,
            ):

                raise TypeError(
                    "isolation_forest must be "
                    "IsolationForestObservationResult "
                    "or None."
                )

            if (
                self.isolation_forest
                .observation_id
                !=
                normalized_id
            ):

                raise ValueError(
                    "Isolation Forest observation "
                    "ID mismatch."
                )

        if (
            self.local_outlier_factor
            is not None
        ):

            if not isinstance(
                self.local_outlier_factor,
                LocalOutlierFactorObservationResult,
            ):

                raise TypeError(
                    "local_outlier_factor must be "
                    "LocalOutlierFactorObservationResult "
                    "or None."
                )

            if (
                self.local_outlier_factor
                .observation_id
                !=
                normalized_id
            ):

                raise ValueError(
                    "LOF observation ID mismatch."
                )

        if self.dbscan is not None:

            if not isinstance(
                self.dbscan,
                DBSCANObservationResult,
            ):

                raise TypeError(
                    "dbscan must be "
                    "DBSCANObservationResult "
                    "or None."
                )

            if (
                self.dbscan
                .observation_id
                !=
                normalized_id
            ):

                raise ValueError(
                    "DBSCAN observation ID mismatch."
                )

    # ==========================================================
    # Independent model flags
    # ==========================================================

    @property
    def isolation_forest_outlier(
        self,
    ) -> (
        bool
        | None
    ):

        if self.isolation_forest is None:

            return None

        return (
            self.isolation_forest
            .is_outlier
        )

    @property
    def local_outlier_factor_outlier(
        self,
    ) -> (
        bool
        | None
    ):

        if (
            self.local_outlier_factor
            is None
        ):

            return None

        return (
            self.local_outlier_factor
            .is_outlier
        )

    @property
    def dbscan_noise(
        self,
    ) -> (
        bool
        | None
    ):

        if self.dbscan is None:

            return None

        return (
            self.dbscan
            .is_noise
        )

    # ==========================================================
    # Outlier model agreement
    # ==========================================================

    @property
    def outlier_method_count(
        self,
    ) -> int:
        """
        Number of independently fitted outlier models
        classifying this observation as an outlier.

        Models counted:

            Isolation Forest
            Local Outlier Factor

        DBSCAN noise is deliberately excluded.

        Range:

            0..2

        This count is NOT a confidence or probability.
        """

        count = 0

        if (
            self.isolation_forest
            is not None
            and
            self.isolation_forest.is_outlier
        ):

            count += 1

        if (
            self.local_outlier_factor
            is not None
            and
            self.local_outlier_factor.is_outlier
        ):

            count += 1

        return count

    @property
    def flagged_by_both_outlier_models(
        self,
    ) -> bool:
        """
        True only when both fitted outlier models classify
        this observation as an outlier.

        Still not evidence or confidence.
        """

        return (
            self.isolation_forest
            is not None
            and
            self.local_outlier_factor
            is not None
            and
            self.isolation_forest.is_outlier
            and
            self.local_outlier_factor.is_outlier
        )

    # ==========================================================
    # DBSCAN convenience
    # ==========================================================

    @property
    def dbscan_cluster_id(
        self,
    ) -> (
        int
        | None
    ):

        if self.dbscan is None:

            return None

        return (
            self.dbscan.cluster_id
        )


# ==========================================================
# Statistics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedAnomalyStatistics:
    """
    Cross-module statistics.

    Counts do not create a combined anomaly score.
    """

    sample_count: int

    feature_count: int

    isolation_forest_scored_count: int

    local_outlier_factor_scored_count: int

    dbscan_assigned_count: int

    isolation_forest_outlier_count: int

    local_outlier_factor_outlier_count: int

    dual_outlier_count: int

    dbscan_cluster_count: int

    dbscan_noise_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "sample_count",
            "feature_count",
            "isolation_forest_scored_count",
            "local_outlier_factor_scored_count",
            "dbscan_assigned_count",
            "isolation_forest_outlier_count",
            "local_outlier_factor_outlier_count",
            "dual_outlier_count",
            "dbscan_cluster_count",
            "dbscan_noise_count",
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

        for field_name in (
            "isolation_forest_scored_count",
            "local_outlier_factor_scored_count",
            "dbscan_assigned_count",
            "isolation_forest_outlier_count",
            "local_outlier_factor_outlier_count",
            "dual_outlier_count",
            "dbscan_noise_count",
        ):

            if (
                getattr(
                    self,
                    field_name,
                )
                >
                self.sample_count
            ):

                raise ValueError(
                    f"{field_name} cannot exceed "
                    "sample_count."
                )

        if (
            self.isolation_forest_outlier_count
            >
            self.isolation_forest_scored_count
        ):

            raise ValueError(
                "Isolation Forest outlier count cannot "
                "exceed scored count."
            )

        if (
            self.local_outlier_factor_outlier_count
            >
            self.local_outlier_factor_scored_count
        ):

            raise ValueError(
                "LOF outlier count cannot "
                "exceed scored count."
            )

        if (
            self.dual_outlier_count
            >
            min(
                self.isolation_forest_outlier_count,
                self.local_outlier_factor_outlier_count,
            )
        ):

            raise ValueError(
                "dual_outlier_count cannot exceed "
                "either model's outlier count."
            )

        if (
            self.dbscan_noise_count
            >
            self.dbscan_assigned_count
        ):

            raise ValueError(
                "DBSCAN noise count cannot exceed "
                "assigned count."
            )


# ==========================================================
# Complete unified result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedAnomalyAnalysisResult:
    """
    Complete Phase 5.4 result.

    All original algorithm results remain available
    independently.
    """

    status: UnifiedAnomalyStatus

    config: UnifiedAnomalyAnalysisConfig

    matrix: NumericFeatureMatrix

    isolation_forest: IsolationForestResult

    local_outlier_factor: LocalOutlierFactorResult

    dbscan: DBSCANClusteringResult

    observations: tuple[
        UnifiedAnomalyObservationResult,
        ...,
    ]

    statistics: UnifiedAnomalyStatistics

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.status,
            UnifiedAnomalyStatus,
        ):

            raise TypeError(
                "status must be "
                "UnifiedAnomalyStatus."
            )

        if not isinstance(
            self.config,
            UnifiedAnomalyAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "UnifiedAnomalyAnalysisConfig."
            )

        if not isinstance(
            self.matrix,
            NumericFeatureMatrix,
        ):

            raise TypeError(
                "matrix must be "
                "NumericFeatureMatrix."
            )

        if not isinstance(
            self.isolation_forest,
            IsolationForestResult,
        ):

            raise TypeError(
                "isolation_forest must be "
                "IsolationForestResult."
            )

        if not isinstance(
            self.local_outlier_factor,
            LocalOutlierFactorResult,
        ):

            raise TypeError(
                "local_outlier_factor must be "
                "LocalOutlierFactorResult."
            )

        if not isinstance(
            self.dbscan,
            DBSCANClusteringResult,
        ):

            raise TypeError(
                "dbscan must be "
                "DBSCANClusteringResult."
            )

        if not isinstance(
            self.observations,
            tuple,
        ):

            raise TypeError(
                "observations must be tuple."
            )

        if not isinstance(
            self.statistics,
            UnifiedAnomalyStatistics,
        ):

            raise TypeError(
                "statistics must be "
                "UnifiedAnomalyStatistics."
            )

        self._validate_feature_contract()

        self._validate_module_sample_counts()

        self._validate_observations()

        self._validate_statistics()

        self._validate_status()

    # ==========================================================
    # Shared feature contract
    # ==========================================================

    def _validate_feature_contract(
        self,
    ) -> None:

        expected = (
            self.matrix.feature_names
        )

        if (
            self.isolation_forest
            .feature_names
            !=
            expected
        ):

            raise ValueError(
                "Isolation Forest feature names "
                "do not match unified matrix."
            )

        if (
            self.local_outlier_factor
            .feature_names
            !=
            expected
        ):

            raise ValueError(
                "LOF feature names do not match "
                "unified matrix."
            )

        if (
            self.dbscan.feature_names
            !=
            expected
        ):

            raise ValueError(
                "DBSCAN feature names do not match "
                "unified matrix."
            )

    # ==========================================================
    # Shared sample count
    # ==========================================================

    def _validate_module_sample_counts(
        self,
    ) -> None:

        expected = (
            self.matrix.sample_count
        )

        if (
            self.isolation_forest
            .sample_count
            !=
            expected
        ):

            raise ValueError(
                "Isolation Forest sample count "
                "does not match unified matrix."
            )

        if (
            self.local_outlier_factor
            .sample_count
            !=
            expected
        ):

            raise ValueError(
                "LOF sample count does not match "
                "unified matrix."
            )

        if (
            self.dbscan.sample_count
            !=
            expected
        ):

            raise ValueError(
                "DBSCAN sample count does not match "
                "unified matrix."
            )

    # ==========================================================
    # Observation alignment
    # ==========================================================

    def _validate_observations(
        self,
    ) -> None:

        if (
            len(
                self.observations
            )
            !=
            self.matrix.sample_count
        ):

            raise ValueError(
                "Unified observation count must "
                "equal matrix sample count."
            )

        expected_ids = (
            self.matrix
            .observation_ids
        )

        actual_ids = tuple(
            item.observation_id
            for item
            in self.observations
        )

        if (
            actual_ids
            !=
            expected_ids
        ):

            raise ValueError(
                "Unified observation order does not "
                "match canonical matrix order."
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    def _validate_statistics(
        self,
    ) -> None:

        expected = (
            UnifiedAnomalyStatistics(
                sample_count=(
                    self.matrix
                    .sample_count
                ),
                feature_count=(
                    self.matrix
                    .feature_count
                ),
                isolation_forest_scored_count=len(
                    self.isolation_forest
                    .observations
                ),
                local_outlier_factor_scored_count=len(
                    self.local_outlier_factor
                    .observations
                ),
                dbscan_assigned_count=len(
                    self.dbscan
                    .observations
                ),
                isolation_forest_outlier_count=(
                    self.isolation_forest
                    .outlier_count
                ),
                local_outlier_factor_outlier_count=(
                    self.local_outlier_factor
                    .outlier_count
                ),
                dual_outlier_count=sum(
                    1
                    for observation
                    in self.observations
                    if (
                        observation
                        .flagged_by_both_outlier_models
                    )
                ),
                dbscan_cluster_count=(
                    self.dbscan
                    .cluster_count
                ),
                dbscan_noise_count=(
                    self.dbscan
                    .noise_count
                ),
            )
        )

        if (
            self.statistics
            !=
            expected
        ):

            raise ValueError(
                "Unified anomaly statistics "
                "are inconsistent."
            )

    # ==========================================================
    # Unified execution status
    # ==========================================================

    def _validate_status(
        self,
    ) -> None:

        expected = (
            self._expected_status(
                sample_count=(
                    self.matrix.sample_count
                ),
                isolation_forest_status=(
                    self.isolation_forest.status
                ),
                local_outlier_factor_status=(
                    self.local_outlier_factor.status
                ),
                dbscan_status=(
                    self.dbscan.status
                ),
            )
        )

        if self.status != expected:

            raise ValueError(
                "Unified anomaly execution status "
                "is inconsistent."
            )

    @staticmethod
    def _expected_status(
        *,
        sample_count: int,
        isolation_forest_status: (
            IsolationForestStatus
        ),
        local_outlier_factor_status: (
            LocalOutlierFactorStatus
        ),
        dbscan_status: DBSCANStatus,
    ) -> UnifiedAnomalyStatus:

        if sample_count == 0:

            return (
                UnifiedAnomalyStatus.EMPTY
            )

        successful_count = sum(
            (
                isolation_forest_status
                ==
                IsolationForestStatus.OK,

                local_outlier_factor_status
                ==
                LocalOutlierFactorStatus.OK,

                dbscan_status
                ==
                DBSCANStatus.OK,
            )
        )

        if successful_count == 3:

            return (
                UnifiedAnomalyStatus.COMPLETE
            )

        if successful_count > 0:

            return (
                UnifiedAnomalyStatus.PARTIAL
            )

        return (
            UnifiedAnomalyStatus.UNAVAILABLE
        )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def sample_count(
        self,
    ) -> int:

        return (
            self.statistics.sample_count
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return (
            self.statistics.feature_count
        )

    @property
    def is_complete(
        self,
    ) -> bool:

        return (
            self.status
            ==
            UnifiedAnomalyStatus.COMPLETE
        )

    @property
    def dual_outliers(
        self,
    ) -> tuple[
        UnifiedAnomalyObservationResult,
        ...,
    ]:
        """
        Observations independently classified as outliers
        by both Isolation Forest and LOF.

        This remains a binary agreement view, not a
        combined score.
        """

        return tuple(
            item
            for item
            in self.observations
            if (
                item
                .flagged_by_both_outlier_models
            )
        )

    @property
    def dbscan_noise_observations(
        self,
    ) -> tuple[
        UnifiedAnomalyObservationResult,
        ...,
    ]:

        return tuple(
            item
            for item
            in self.observations
            if item.dbscan_noise
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_observation(
        self,
        observation_id: str,
    ) -> UnifiedAnomalyObservationResult:

        target = (
            str(
                observation_id
            )
            .strip()
        )

        for item in self.observations:

            if (
                item.observation_id
                ==
                target
            ):

                return item

        raise KeyError(
            "Unified anomaly observation "
            "not found."
        )

    # ==========================================================
    # Independent ranking access
    # ==========================================================

    def top_isolation_forest_anomalies(
        self,
        limit: int = 10,
    ):

        return (
            self.isolation_forest
            .top_anomalies(
                limit
            )
        )

    def top_local_outlier_factor_anomalies(
        self,
        limit: int = 10,
    ):

        return (
            self.local_outlier_factor
            .top_anomalies(
                limit
            )
        )


# ==========================================================
# Service
# ==========================================================


class UnifiedAnomalyAnalysisService:
    """
    Executes Phase 5.1–5.3 over one shared numerical
    feature matrix.

    Each algorithm executes independently exactly once.
    """

    def __init__(
        self,
        isolation_forest_service: (
            IsolationForestAnomalyService
            | None
        ) = None,
        local_outlier_factor_service: (
            LocalOutlierFactorAnomalyService
            | None
        ) = None,
        dbscan_service: (
            DBSCANClusteringService
            | None
        ) = None,
    ) -> None:

        if (
            isolation_forest_service
            is not None
            and
            not isinstance(
                isolation_forest_service,
                IsolationForestAnomalyService,
            )
        ):

            raise TypeError(
                "isolation_forest_service must be "
                "IsolationForestAnomalyService."
            )

        if (
            local_outlier_factor_service
            is not None
            and
            not isinstance(
                local_outlier_factor_service,
                LocalOutlierFactorAnomalyService,
            )
        ):

            raise TypeError(
                "local_outlier_factor_service must be "
                "LocalOutlierFactorAnomalyService."
            )

        if (
            dbscan_service
            is not None
            and
            not isinstance(
                dbscan_service,
                DBSCANClusteringService,
            )
        ):

            raise TypeError(
                "dbscan_service must be "
                "DBSCANClusteringService."
            )

        self.isolation_forest_service = (
            isolation_forest_service
            or
            IsolationForestAnomalyService()
        )

        self.local_outlier_factor_service = (
            local_outlier_factor_service
            or
            LocalOutlierFactorAnomalyService()
        )

        self.dbscan_service = (
            dbscan_service
            or
            DBSCANClusteringService()
        )

    # ==========================================================
    # Complete analysis
    # ==========================================================

    def analyze(
        self,
        matrix: NumericFeatureMatrix,
        config: (
            UnifiedAnomalyAnalysisConfig
            | None
        ) = None,
    ) -> UnifiedAnomalyAnalysisResult:
        """
        Execute Isolation Forest, LOF and DBSCAN.

        Raw numerical scores remain independent.

        No database persistence is performed.
        """

        if not isinstance(
            matrix,
            NumericFeatureMatrix,
        ):

            raise TypeError(
                "matrix must be "
                "NumericFeatureMatrix."
            )

        config = (
            config
            or
            UnifiedAnomalyAnalysisConfig()
        )

        if not isinstance(
            config,
            UnifiedAnomalyAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "UnifiedAnomalyAnalysisConfig."
            )

        # ======================================================
        # One shared deterministic matrix
        # ======================================================

        matrix = (
            matrix.canonicalized()
        )

        # ======================================================
        # 5.1 Isolation Forest
        # ======================================================

        isolation_forest = (
            self.isolation_forest_service
            .analyze(
                matrix,
                config.isolation_forest,
            )
        )

        # ======================================================
        # 5.2 LOF
        # ======================================================

        local_outlier_factor = (
            self.local_outlier_factor_service
            .analyze(
                matrix,
                config.local_outlier_factor,
            )
        )

        # ======================================================
        # 5.3 DBSCAN
        # ======================================================

        dbscan = (
            self.dbscan_service
            .analyze(
                matrix,
                config.dbscan,
            )
        )

        # ======================================================
        # Result maps
        # ======================================================

        isolation_map = {
            item.observation_id:
                item
            for item
            in isolation_forest.observations
        }

        lof_map = {
            item.observation_id:
                item
            for item
            in local_outlier_factor.observations
        }

        dbscan_map = {
            item.observation_id:
                item
            for item
            in dbscan.observations
        }

        # ======================================================
        # Unified observation alignment
        # ======================================================

        observations = tuple(
            UnifiedAnomalyObservationResult(
                observation_id=(
                    observation
                    .observation_id
                ),
                isolation_forest=(
                    isolation_map.get(
                        observation
                        .observation_id
                    )
                ),
                local_outlier_factor=(
                    lof_map.get(
                        observation
                        .observation_id
                    )
                ),
                dbscan=(
                    dbscan_map.get(
                        observation
                        .observation_id
                    )
                ),
            )
            for observation
            in matrix.observations
        )

        # ======================================================
        # Statistics
        # ======================================================

        statistics = (
            UnifiedAnomalyStatistics(
                sample_count=(
                    matrix.sample_count
                ),
                feature_count=(
                    matrix.feature_count
                ),
                isolation_forest_scored_count=len(
                    isolation_forest
                    .observations
                ),
                local_outlier_factor_scored_count=len(
                    local_outlier_factor
                    .observations
                ),
                dbscan_assigned_count=len(
                    dbscan.observations
                ),
                isolation_forest_outlier_count=(
                    isolation_forest
                    .outlier_count
                ),
                local_outlier_factor_outlier_count=(
                    local_outlier_factor
                    .outlier_count
                ),
                dual_outlier_count=sum(
                    1
                    for item
                    in observations
                    if (
                        item
                        .flagged_by_both_outlier_models
                    )
                ),
                dbscan_cluster_count=(
                    dbscan.cluster_count
                ),
                dbscan_noise_count=(
                    dbscan.noise_count
                ),
            )
        )

        # ======================================================
        # Unified execution status
        # ======================================================

        status = (
            UnifiedAnomalyAnalysisResult
            ._expected_status(
                sample_count=(
                    matrix.sample_count
                ),
                isolation_forest_status=(
                    isolation_forest.status
                ),
                local_outlier_factor_status=(
                    local_outlier_factor.status
                ),
                dbscan_status=(
                    dbscan.status
                ),
            )
        )

        return (
            UnifiedAnomalyAnalysisResult(
                status=status,
                config=config,
                matrix=matrix,
                isolation_forest=(
                    isolation_forest
                ),
                local_outlier_factor=(
                    local_outlier_factor
                ),
                dbscan=dbscan,
                observations=(
                    observations
                ),
                statistics=(
                    statistics
                ),
            )
        )