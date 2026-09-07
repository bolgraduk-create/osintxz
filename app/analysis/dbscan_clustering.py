"""
DBSCAN density-based clustering.

Phase 5.3.

Pipeline:

NumericFeatureMatrix
    ↓
validation
    ↓
deterministic row ordering
    ↓
optional feature standardization
    ↓
DBSCAN
    ↓
raw sklearn cluster labels
    ↓
canonical cluster ID normalization
    ↓
core / border / noise classification
    ↓
DBSCANClusteringResult

Important semantics:

DBSCAN cluster
    != relationship

DBSCAN noise
    != anomaly proof
    != Isolation Forest outlier
    != LOF outlier
    != suspicious activity
    != malicious activity
    != evidence
    != identity signal

DBSCAN produces density-based structural grouping.

It does NOT produce:

- anomaly score
- anomaly confidence
- evidence confidence
- identity confidence
- relationship confidence

This module does NOT:

- query the database
- write to the database
- create Evidence
- create Relationships
- merge Entities
- infer intent
- infer criminality
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import isfinite

import numpy as np

from sklearn.cluster import (
    DBSCAN,
)

from sklearn.preprocessing import (
    StandardScaler,
)

from app.analysis.anomaly_contracts import (
    NumericFeatureMatrix,
)


# ==========================================================
# Status
# ==========================================================


class DBSCANStatus(
    str,
    Enum,
):
    """
    Execution status.
    """

    OK = "ok"

    EMPTY = "empty"

    INSUFFICIENT_SAMPLES = (
        "insufficient_samples"
    )

    NO_VARIATION = (
        "no_variation"
    )


# ==========================================================
# Point type
# ==========================================================


class DBSCANPointType(
    str,
    Enum,
):
    """
    Density role assigned by DBSCAN.

    CORE:
        Dense point satisfying the DBSCAN core criterion.

    BORDER:
        Non-core point belonging to a cluster because it
        is reachable from a core point.

    NOISE:
        Point not assigned to any density cluster.

        NOISE does not automatically mean anomaly.
    """

    CORE = "core"

    BORDER = "border"

    NOISE = "noise"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DBSCANConfig:
    """
    DBSCAN configuration.

    eps:

        Maximum neighborhood distance.

        This parameter is intentionally NOT selected
        automatically because its correct value depends
        on feature geometry and domain scale.

    min_samples:

        DBSCAN density threshold.

        Includes the point itself, matching sklearn
        semantics.

    standardize:

        Standardize features before distance calculation.

        Enabled by default because DBSCAN is
        distance-based.

    metric:

        Distance metric accepted by sklearn DBSCAN.

    p:

        Minkowski power when applicable.

        None leaves sklearn's metric-specific default.

    minimum_input_samples:

        Application-level guard.

        Analysis is not fitted when fewer observations
        exist than this value.

        This is separate from DBSCAN min_samples.
    """

    eps: float = 0.5

    min_samples: int = 5

    standardize: bool = True

    metric: str = "euclidean"

    p: (
        float
        | None
    ) = None

    algorithm: str = "auto"

    leaf_size: int = 30

    n_jobs: (
        int
        | None
    ) = 1

    minimum_input_samples: int = 5

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # eps
        # ======================================================

        eps = float(
            self.eps
        )

        if (
            not isfinite(
                eps
            )
            or eps <= 0.0
        ):

            raise ValueError(
                "eps must be finite and positive."
            )

        object.__setattr__(
            self,
            "eps",
            eps,
        )

        # ======================================================
        # min_samples
        # ======================================================

        if (
            not isinstance(
                self.min_samples,
                int,
            )
            or isinstance(
                self.min_samples,
                bool,
            )
            or self.min_samples < 2
        ):

            raise ValueError(
                "min_samples must be "
                "an integer >= 2."
            )

        # ======================================================
        # standardize
        # ======================================================

        if not isinstance(
            self.standardize,
            bool,
        ):

            raise TypeError(
                "standardize must be bool."
            )

        # ======================================================
        # metric
        # ======================================================

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

        normalized_metric = (
            self.metric.strip()
        )

        if normalized_metric == "precomputed":

            raise ValueError(
                "metric='precomputed' is not supported "
                "by NumericFeatureMatrix DBSCAN."
            )

        object.__setattr__(
            self,
            "metric",
            normalized_metric,
        )

        # ======================================================
        # p
        # ======================================================

        if self.p is not None:

            p = float(
                self.p
            )

            if (
                not isfinite(
                    p
                )
                or p <= 0.0
            ):

                raise ValueError(
                    "p must be finite and positive."
                )

            object.__setattr__(
                self,
                "p",
                p,
            )

        # ======================================================
        # algorithm
        # ======================================================

        if self.algorithm not in (
            "auto",
            "ball_tree",
            "kd_tree",
            "brute",
        ):

            raise ValueError(
                "Unsupported DBSCAN algorithm."
            )

        # ======================================================
        # leaf_size
        # ======================================================

        if (
            not isinstance(
                self.leaf_size,
                int,
            )
            or isinstance(
                self.leaf_size,
                bool,
            )
            or self.leaf_size < 1
        ):

            raise ValueError(
                "leaf_size must be "
                "a positive integer."
            )

        # ======================================================
        # n_jobs
        # ======================================================

        if self.n_jobs is not None:

            if (
                not isinstance(
                    self.n_jobs,
                    int,
                )
                or isinstance(
                    self.n_jobs,
                    bool,
                )
                or self.n_jobs == 0
            ):

                raise ValueError(
                    "n_jobs must be None or "
                    "a non-zero integer."
                )

        # ======================================================
        # minimum input samples
        # ======================================================

        if (
            not isinstance(
                self.minimum_input_samples,
                int,
            )
            or isinstance(
                self.minimum_input_samples,
                bool,
            )
            or self.minimum_input_samples < 2
        ):

            raise ValueError(
                "minimum_input_samples must "
                "be an integer >= 2."
            )


# ==========================================================
# Observation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DBSCANObservationResult:
    """
    DBSCAN membership result for one observation.

    cluster_id:

        Canonical non-negative cluster identifier.

        None for noise.

    point_type:

        CORE / BORDER / NOISE.

    There is intentionally no anomaly score.
    """

    observation_id: str

    cluster_id: (
        int
        | None
    )

    point_type: DBSCANPointType

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

        object.__setattr__(
            self,
            "observation_id",
            self.observation_id.strip(),
        )

        if not isinstance(
            self.point_type,
            DBSCANPointType,
        ):

            raise TypeError(
                "point_type must be "
                "DBSCANPointType."
            )

        if (
            self.point_type
            ==
            DBSCANPointType.NOISE
        ):

            if self.cluster_id is not None:

                raise ValueError(
                    "Noise point cannot have "
                    "cluster_id."
                )

        else:

            if (
                not isinstance(
                    self.cluster_id,
                    int,
                )
                or isinstance(
                    self.cluster_id,
                    bool,
                )
                or self.cluster_id < 0
            ):

                raise ValueError(
                    "Cluster member requires "
                    "non-negative cluster_id."
                )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def is_noise(
        self,
    ) -> bool:

        return (
            self.point_type
            ==
            DBSCANPointType.NOISE
        )

    @property
    def is_core(
        self,
    ) -> bool:

        return (
            self.point_type
            ==
            DBSCANPointType.CORE
        )

    @property
    def is_border(
        self,
    ) -> bool:

        return (
            self.point_type
            ==
            DBSCANPointType.BORDER
        )


# ==========================================================
# Cluster summary
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DBSCANClusterSummary:
    """
    One canonical DBSCAN cluster.
    """

    cluster_id: int

    member_ids: tuple[
        str,
        ...,
    ]

    core_member_ids: tuple[
        str,
        ...,
    ]

    border_member_ids: tuple[
        str,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.cluster_id,
                int,
            )
            or isinstance(
                self.cluster_id,
                bool,
            )
            or self.cluster_id < 0
        ):

            raise ValueError(
                "cluster_id must be "
                "non-negative integer."
            )

        for field_name in (
            "member_ids",
            "core_member_ids",
            "border_member_ids",
        ):

            value = getattr(
                self,
                field_name,
            )

            if not isinstance(
                value,
                tuple,
            ):

                raise TypeError(
                    f"{field_name} must be tuple."
                )

            if len(
                value
            ) != len(
                set(
                    value
                )
            ):

                raise ValueError(
                    f"{field_name} contains duplicates."
                )

            if tuple(
                sorted(
                    value
                )
            ) != value:

                raise ValueError(
                    f"{field_name} must be "
                    "deterministically sorted."
                )

        if not self.member_ids:

            raise ValueError(
                "Cluster cannot be empty."
            )

        member_set = set(
            self.member_ids
        )

        core_set = set(
            self.core_member_ids
        )

        border_set = set(
            self.border_member_ids
        )

        if (
            core_set
            &
            border_set
        ):

            raise ValueError(
                "Core and border members "
                "cannot overlap."
            )

        if (
            core_set
            |
            border_set
        ) != member_set:

            raise ValueError(
                "Core + border members must "
                "equal cluster membership."
            )

        if not self.core_member_ids:

            raise ValueError(
                "DBSCAN cluster requires "
                "at least one core point."
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def member_count(
        self,
    ) -> int:

        return len(
            self.member_ids
        )

    @property
    def core_count(
        self,
    ) -> int:

        return len(
            self.core_member_ids
        )

    @property
    def border_count(
        self,
    ) -> int:

        return len(
            self.border_member_ids
        )


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DBSCANDiagnostics:
    """
    Non-interpretive DBSCAN diagnostics.
    """

    sample_count: int

    feature_count: int

    constant_feature_names: tuple[
        str,
        ...,
    ]

    variable_feature_count: int

    standardized: bool

    cluster_count: int

    core_point_count: int

    border_point_count: int

    noise_point_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "sample_count",
            "feature_count",
            "variable_feature_count",
            "cluster_count",
            "core_point_count",
            "border_point_count",
            "noise_point_count",
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
            self.constant_feature_names,
            tuple,
        ):

            raise TypeError(
                "constant_feature_names "
                "must be tuple."
            )

        if not isinstance(
            self.standardized,
            bool,
        ):

            raise TypeError(
                "standardized must be bool."
            )

        if (
            self.variable_feature_count
            +
            len(
                self.constant_feature_names
            )
            !=
            self.feature_count
        ):

            raise ValueError(
                "Constant + variable features "
                "must equal feature_count."
            )

        assigned_count = (
            self.core_point_count
            +
            self.border_point_count
            +
            self.noise_point_count
        )

        if (
            assigned_count
            not in (
                0,
                self.sample_count,
            )
        ):

            raise ValueError(
                "DBSCAN point counts must be "
                "zero for unfitted result or "
                "equal sample_count."
            )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DBSCANClusteringResult:
    """
    Complete Phase 5.3 DBSCAN result.
    """

    status: DBSCANStatus

    config: DBSCANConfig

    feature_names: tuple[
        str,
        ...,
    ]

    observations: tuple[
        DBSCANObservationResult,
        ...,
    ]

    clusters: tuple[
        DBSCANClusterSummary,
        ...,
    ]

    diagnostics: DBSCANDiagnostics

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.status,
            DBSCANStatus,
        ):

            raise TypeError(
                "status must be DBSCANStatus."
            )

        if not isinstance(
            self.config,
            DBSCANConfig,
        ):

            raise TypeError(
                "config must be DBSCANConfig."
            )

        if not isinstance(
            self.feature_names,
            tuple,
        ):

            raise TypeError(
                "feature_names must be tuple."
            )

        if not isinstance(
            self.observations,
            tuple,
        ):

            raise TypeError(
                "observations must be tuple."
            )

        if not isinstance(
            self.clusters,
            tuple,
        ):

            raise TypeError(
                "clusters must be tuple."
            )

        if not isinstance(
            self.diagnostics,
            DBSCANDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "DBSCANDiagnostics."
            )

        if (
            len(
                self.feature_names
            )
            !=
            self.diagnostics.feature_count
        ):

            raise ValueError(
                "Feature count mismatch."
            )

        if (
            self.status
            ==
            DBSCANStatus.OK
        ):

            if (
                len(
                    self.observations
                )
                !=
                self.diagnostics.sample_count
            ):

                raise ValueError(
                    "Successful DBSCAN result must "
                    "contain one result per sample."
                )

            if (
                len(
                    self.clusters
                )
                !=
                self.diagnostics.cluster_count
            ):

                raise ValueError(
                    "Cluster count mismatch."
                )

            expected_cluster_ids = tuple(
                range(
                    len(
                        self.clusters
                    )
                )
            )

            actual_cluster_ids = tuple(
                cluster.cluster_id
                for cluster
                in self.clusters
            )

            if (
                actual_cluster_ids
                !=
                expected_cluster_ids
            ):

                raise ValueError(
                    "Canonical DBSCAN cluster IDs "
                    "must form 0..K-1."
                )

            core_count = sum(
                1
                for item
                in self.observations
                if item.is_core
            )

            border_count = sum(
                1
                for item
                in self.observations
                if item.is_border
            )

            noise_count = sum(
                1
                for item
                in self.observations
                if item.is_noise
            )

            if (
                core_count
                !=
                self.diagnostics.core_point_count
            ):

                raise ValueError(
                    "Core point count mismatch."
                )

            if (
                border_count
                !=
                self.diagnostics.border_point_count
            ):

                raise ValueError(
                    "Border point count mismatch."
                )

            if (
                noise_count
                !=
                self.diagnostics.noise_point_count
            ):

                raise ValueError(
                    "Noise point count mismatch."
                )

            cluster_members_from_points: dict[
                int,
                set[
                    str
                ],
            ] = {}

            for item in self.observations:

                if item.cluster_id is None:

                    continue

                cluster_members_from_points.setdefault(
                    item.cluster_id,
                    set(),
                ).add(
                    item.observation_id
                )

            for cluster in self.clusters:

                if (
                    cluster_members_from_points.get(
                        cluster.cluster_id,
                        set(),
                    )
                    !=
                    set(
                        cluster.member_ids
                    )
                ):

                    raise ValueError(
                        "Cluster membership mismatch."
                    )

        else:

            if self.observations:

                raise ValueError(
                    "Unfitted DBSCAN result cannot "
                    "contain assignments."
                )

            if self.clusters:

                raise ValueError(
                    "Unfitted DBSCAN result cannot "
                    "contain clusters."
                )

            if (
                self.diagnostics.cluster_count != 0
                or
                self.diagnostics.core_point_count != 0
                or
                self.diagnostics.border_point_count != 0
                or
                self.diagnostics.noise_point_count != 0
            ):

                raise ValueError(
                    "Unfitted DBSCAN result cannot "
                    "contain clustering counts."
                )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def sample_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .sample_count
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .feature_count
        )

    @property
    def cluster_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .cluster_count
        )

    @property
    def noise_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .noise_point_count
        )

    @property
    def is_fitted(
        self,
    ) -> bool:

        return (
            self.status
            ==
            DBSCANStatus.OK
        )

    @property
    def noise_observations(
        self,
    ) -> tuple[
        DBSCANObservationResult,
        ...,
    ]:

        return tuple(
            item
            for item
            in self.observations
            if item.is_noise
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_observation(
        self,
        observation_id: str,
    ) -> DBSCANObservationResult:

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
            "DBSCAN observation not found."
        )

    def get_cluster(
        self,
        cluster_id: int,
    ) -> DBSCANClusterSummary:

        if (
            not isinstance(
                cluster_id,
                int,
            )
            or isinstance(
                cluster_id,
                bool,
            )
            or cluster_id < 0
        ):

            raise ValueError(
                "cluster_id must be "
                "non-negative integer."
            )

        for cluster in self.clusters:

            if (
                cluster.cluster_id
                ==
                cluster_id
            ):

                return cluster

        raise KeyError(
            "DBSCAN cluster not found."
        )


# ==========================================================
# Service
# ==========================================================


class DBSCANClusteringService:
    """
    Pure DBSCAN clustering service.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        matrix: NumericFeatureMatrix,
        config: (
            DBSCANConfig
            | None
        ) = None,
    ) -> DBSCANClusteringResult:
        """
        Perform density-based clustering.

        No database access or persistence is performed.
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
            DBSCANConfig()
        )

        if not isinstance(
            config,
            DBSCANConfig,
        ):

            raise TypeError(
                "config must be DBSCANConfig."
            )

        # ======================================================
        # Canonical input order
        # ======================================================

        matrix = (
            matrix.canonicalized()
        )

        # ======================================================
        # Empty
        # ======================================================

        if matrix.sample_count == 0:

            return self._unfitted_result(
                matrix,
                config,
                status=(
                    DBSCANStatus.EMPTY
                ),
                constant_feature_names=(),
            )

        # ======================================================
        # Numerical values
        # ======================================================

        values = np.asarray(
            [
                observation.values
                for observation
                in matrix.observations
            ],
            dtype=np.float64,
        )

        constant_feature_names = (
            self._constant_feature_names(
                values,
                matrix.feature_names,
            )
        )

        # ======================================================
        # Insufficient sample guard
        # ======================================================

        required_samples = max(
            config.minimum_input_samples,
            config.min_samples,
        )

        if (
            matrix.sample_count
            <
            required_samples
        ):

            return self._unfitted_result(
                matrix,
                config,
                status=(
                    DBSCANStatus
                    .INSUFFICIENT_SAMPLES
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # No numerical variation
        # ======================================================

        if (
            len(
                constant_feature_names
            )
            ==
            matrix.feature_count
        ):

            return self._unfitted_result(
                matrix,
                config,
                status=(
                    DBSCANStatus.NO_VARIATION
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # Standardization
        # ======================================================

        if config.standardize:

            scaler = (
                StandardScaler()
            )

            model_values = (
                scaler.fit_transform(
                    values
                )
            )

        else:

            model_values = values

        # ======================================================
        # Fit DBSCAN
        # ======================================================

        model = DBSCAN(
            eps=(
                config.eps
            ),
            min_samples=(
                config.min_samples
            ),
            metric=(
                config.metric
            ),
            algorithm=(
                config.algorithm
            ),
            leaf_size=(
                config.leaf_size
            ),
            p=(
                config.p
            ),
            n_jobs=(
                config.n_jobs
            ),
        )

        raw_labels = (
            model.fit_predict(
                model_values
            )
        )

        raw_labels = np.asarray(
            raw_labels,
            dtype=np.int64,
        )

        core_indices = {
            int(
                index
            )
            for index
            in model.core_sample_indices_
        }

        # ======================================================
        # Canonicalize cluster IDs
        #
        # sklearn's non-negative label numbers are not
        # treated as semantic identifiers.
        #
        # We order discovered clusters by the smallest
        # observation ID belonging to each cluster.
        # ======================================================

        cluster_id_map = (
            self._canonical_cluster_id_map(
                raw_labels,
                matrix,
            )
        )

        # ======================================================
        # Observation assignments
        # ======================================================

        observation_results: list[
            DBSCANObservationResult
        ] = []

        for index, observation in enumerate(
            matrix.observations
        ):

            raw_label = int(
                raw_labels[
                    index
                ]
            )

            if raw_label == -1:

                cluster_id = None

                point_type = (
                    DBSCANPointType.NOISE
                )

            else:

                cluster_id = (
                    cluster_id_map[
                        raw_label
                    ]
                )

                if index in core_indices:

                    point_type = (
                        DBSCANPointType.CORE
                    )

                else:

                    point_type = (
                        DBSCANPointType.BORDER
                    )

            observation_results.append(
                DBSCANObservationResult(
                    observation_id=(
                        observation
                        .observation_id
                    ),
                    cluster_id=(
                        cluster_id
                    ),
                    point_type=(
                        point_type
                    ),
                )
            )

        observation_tuple = tuple(
            observation_results
        )

        # ======================================================
        # Cluster summaries
        # ======================================================

        clusters = (
            self._build_cluster_summaries(
                observation_tuple
            )
        )

        # ======================================================
        # Diagnostics
        # ======================================================

        core_count = sum(
            1
            for item
            in observation_tuple
            if item.is_core
        )

        border_count = sum(
            1
            for item
            in observation_tuple
            if item.is_border
        )

        noise_count = sum(
            1
            for item
            in observation_tuple
            if item.is_noise
        )

        diagnostics = (
            DBSCANDiagnostics(
                sample_count=(
                    matrix.sample_count
                ),
                feature_count=(
                    matrix.feature_count
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
                variable_feature_count=(
                    matrix.feature_count
                    -
                    len(
                        constant_feature_names
                    )
                ),
                standardized=(
                    config.standardize
                ),
                cluster_count=len(
                    clusters
                ),
                core_point_count=(
                    core_count
                ),
                border_point_count=(
                    border_count
                ),
                noise_point_count=(
                    noise_count
                ),
            )
        )

        return (
            DBSCANClusteringResult(
                status=(
                    DBSCANStatus.OK
                ),
                config=config,
                feature_names=(
                    matrix.feature_names
                ),
                observations=(
                    observation_tuple
                ),
                clusters=(
                    clusters
                ),
                diagnostics=(
                    diagnostics
                ),
            )
        )

    # ==========================================================
    # Canonical cluster IDs
    # ==========================================================

    @staticmethod
    def _canonical_cluster_id_map(
        raw_labels: np.ndarray,
        matrix: NumericFeatureMatrix,
    ) -> dict[
        int,
        int,
    ]:
        """
        Convert sklearn cluster labels into deterministic
        canonical IDs.

        Noise label -1 is excluded.
        """

        members_by_raw_cluster: dict[
            int,
            list[
                str
            ],
        ] = {}

        for index, raw_value in enumerate(
            raw_labels
        ):

            raw_label = int(
                raw_value
            )

            if raw_label == -1:

                continue

            members_by_raw_cluster.setdefault(
                raw_label,
                [],
            ).append(
                matrix
                .observations[
                    index
                ]
                .observation_id
            )

        ordered_raw_labels = sorted(
            members_by_raw_cluster,
            key=lambda raw_label: (
                min(
                    members_by_raw_cluster[
                        raw_label
                    ]
                )
            ),
        )

        return {
            raw_label:
                canonical_id
            for canonical_id, raw_label
            in enumerate(
                ordered_raw_labels
            )
        }

    # ==========================================================
    # Cluster summaries
    # ==========================================================

    @staticmethod
    def _build_cluster_summaries(
        observations: tuple[
            DBSCANObservationResult,
            ...,
        ],
    ) -> tuple[
        DBSCANClusterSummary,
        ...,
    ]:

        members: dict[
            int,
            list[
                str
            ],
        ] = {}

        core_members: dict[
            int,
            list[
                str
            ],
        ] = {}

        border_members: dict[
            int,
            list[
                str
            ],
        ] = {}

        for item in observations:

            if item.cluster_id is None:

                continue

            cluster_id = (
                item.cluster_id
            )

            members.setdefault(
                cluster_id,
                [],
            ).append(
                item.observation_id
            )

            if item.is_core:

                core_members.setdefault(
                    cluster_id,
                    [],
                ).append(
                    item.observation_id
                )

            elif item.is_border:

                border_members.setdefault(
                    cluster_id,
                    [],
                ).append(
                    item.observation_id
                )

        summaries: list[
            DBSCANClusterSummary
        ] = []

        for cluster_id in sorted(
            members
        ):

            summaries.append(
                DBSCANClusterSummary(
                    cluster_id=(
                        cluster_id
                    ),
                    member_ids=tuple(
                        sorted(
                            members[
                                cluster_id
                            ]
                        )
                    ),
                    core_member_ids=tuple(
                        sorted(
                            core_members.get(
                                cluster_id,
                                [],
                            )
                        )
                    ),
                    border_member_ids=tuple(
                        sorted(
                            border_members.get(
                                cluster_id,
                                [],
                            )
                        )
                    ),
                )
            )

        return tuple(
            summaries
        )

    # ==========================================================
    # Constant features
    # ==========================================================

    @staticmethod
    def _constant_feature_names(
        values: np.ndarray,
        feature_names: tuple[
            str,
            ...,
        ],
    ) -> tuple[
        str,
        ...,
    ]:

        if values.shape[
            0
        ] == 0:

            return ()

        result: list[
            str
        ] = []

        for feature_index, name in enumerate(
            feature_names
        ):

            column = values[
                :,
                feature_index
            ]

            if np.all(
                column
                ==
                column[
                    0
                ]
            ):

                result.append(
                    name
                )

        return tuple(
            result
        )

    # ==========================================================
    # Unfitted result
    # ==========================================================

    @staticmethod
    def _unfitted_result(
        matrix: NumericFeatureMatrix,
        config: DBSCANConfig,
        *,
        status: DBSCANStatus,
        constant_feature_names: tuple[
            str,
            ...,
        ],
    ) -> DBSCANClusteringResult:

        diagnostics = (
            DBSCANDiagnostics(
                sample_count=(
                    matrix.sample_count
                ),
                feature_count=(
                    matrix.feature_count
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
                variable_feature_count=(
                    matrix.feature_count
                    -
                    len(
                        constant_feature_names
                    )
                ),
                standardized=(
                    config.standardize
                ),
                cluster_count=0,
                core_point_count=0,
                border_point_count=0,
                noise_point_count=0,
            )
        )

        return (
            DBSCANClusteringResult(
                status=status,
                config=config,
                feature_names=(
                    matrix.feature_names
                ),
                observations=(),
                clusters=(),
                diagnostics=(
                    diagnostics
                ),
            )
        )