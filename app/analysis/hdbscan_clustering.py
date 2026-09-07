"""
Hierarchical density-based clustering.

Block 7 — Clustering.

This module adds HDBSCAN as an independent analytical
clustering mechanism over the existing NumericFeatureMatrix
contract.

Architecture:

NumericFeatureMatrix
        ↓
canonical ordering
        ↓
optional StandardScaler
        ↓
sklearn.cluster.HDBSCAN
        ↓
raw cluster labels + membership probabilities
        ↓
canonical cluster ID normalization
        ↓
HDBSCANClusteringResult

Important semantic boundaries:

HDBSCAN cluster
    != Graph community

HDBSCAN cluster
    != Relationship

HDBSCAN noise
    != anomaly proof

HDBSCAN noise
    != suspicious / malicious entity

membership_probability
    != Evidence confidence

membership_probability
    != Entity Resolution confidence

This module performs no:

- database access
- database writes
- Entity mutation
- Relationship creation
- Evidence creation
- Entity Resolution
- graph mutation
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

import numpy as np

from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import StandardScaler

from app.analysis.anomaly_contracts import (
    NumericFeatureMatrix,
)


# ==========================================================
# Status
# ==========================================================


class HDBSCANStatus(
    str,
    Enum,
):
    """
    Execution status.

    Status represents whether clustering could be
    meaningfully executed.

    It is not an analytical confidence value.
    """

    OK = "ok"

    EMPTY = "empty"

    INSUFFICIENT_SAMPLES = (
        "insufficient_samples"
    )

    NO_VARIATION = "no_variation"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HDBSCANConfig:
    """
    HDBSCAN execution configuration.

    Defaults intentionally stay conservative.

    `copy=True` is explicit because scikit-learn changes
    the default in 1.10. Keeping it explicit prevents a
    version-dependent behavioural warning.
    """

    min_cluster_size: int = 5

    min_samples: (
        int
        | None
    ) = None

    cluster_selection_epsilon: float = (
        0.0
    )

    max_cluster_size: (
        int
        | None
    ) = None

    standardize: bool = True

    metric: str = "euclidean"

    alpha: float = 1.0

    algorithm: str = "auto"

    leaf_size: int = 40

    n_jobs: (
        int
        | None
    ) = 1

    cluster_selection_method: str = (
        "eom"
    )

    allow_single_cluster: bool = False

    copy: bool = True

    minimum_input_samples: int = 5

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # min_cluster_size
        # ======================================================

        if (
            not isinstance(
                self.min_cluster_size,
                int,
            )
            or isinstance(
                self.min_cluster_size,
                bool,
            )
            or self.min_cluster_size < 2
        ):

            raise ValueError(
                "min_cluster_size must be an "
                "integer >= 2."
            )

        # ======================================================
        # min_samples
        # ======================================================

        if (
            self.min_samples
            is not None
        ):

            if (
                not isinstance(
                    self.min_samples,
                    int,
                )
                or isinstance(
                    self.min_samples,
                    bool,
                )
                or self.min_samples < 1
            ):

                raise ValueError(
                    "min_samples must be None "
                    "or an integer >= 1."
                )

        # ======================================================
        # cluster_selection_epsilon
        # ======================================================

        epsilon = float(
            self.cluster_selection_epsilon
        )

        if (
            not isfinite(
                epsilon
            )
            or epsilon < 0.0
        ):

            raise ValueError(
                "cluster_selection_epsilon must "
                "be finite and non-negative."
            )

        object.__setattr__(
            self,
            "cluster_selection_epsilon",
            epsilon,
        )

        # ======================================================
        # max_cluster_size
        # ======================================================

        if (
            self.max_cluster_size
            is not None
        ):

            if (
                not isinstance(
                    self.max_cluster_size,
                    int,
                )
                or isinstance(
                    self.max_cluster_size,
                    bool,
                )
                or self.max_cluster_size < 1
            ):

                raise ValueError(
                    "max_cluster_size must be None "
                    "or an integer >= 1."
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
            or
            not self.metric.strip()
        ):

            raise ValueError(
                "metric cannot be empty."
            )

        object.__setattr__(
            self,
            "metric",
            self.metric.strip(),
        )

        # ======================================================
        # alpha
        # ======================================================

        alpha = float(
            self.alpha
        )

        if (
            not isfinite(
                alpha
            )
            or alpha <= 0.0
        ):

            raise ValueError(
                "alpha must be finite and positive."
            )

        object.__setattr__(
            self,
            "alpha",
            alpha,
        )

        # ======================================================
        # algorithm
        # ======================================================

        if (
            not isinstance(
                self.algorithm,
                str,
            )
            or
            not self.algorithm.strip()
        ):

            raise ValueError(
                "algorithm cannot be empty."
            )

        object.__setattr__(
            self,
            "algorithm",
            self.algorithm.strip(),
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
                "leaf_size must be an integer >= 1."
            )

        # ======================================================
        # n_jobs
        # ======================================================

        if (
            self.n_jobs
            is not None
        ):

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
        # cluster selection method
        # ======================================================

        if (
            self.cluster_selection_method
            not in
            {
                "eom",
                "leaf",
            }
        ):

            raise ValueError(
                "cluster_selection_method must "
                "be 'eom' or 'leaf'."
            )

        # ======================================================
        # allow_single_cluster / copy
        # ======================================================

        if not isinstance(
            self.allow_single_cluster,
            bool,
        ):

            raise TypeError(
                "allow_single_cluster must be bool."
            )

        if not isinstance(
            self.copy,
            bool,
        ):

            raise TypeError(
                "copy must be bool."
            )

        # ======================================================
        # minimum_input_samples
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
            or self.minimum_input_samples < 1
        ):

            raise ValueError(
                "minimum_input_samples must be "
                "an integer >= 1."
            )


# ==========================================================
# Observation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HDBSCANObservationResult:
    """
    HDBSCAN assignment for one numerical observation.

    `membership_probability` describes how strongly the
    observation belongs to its HDBSCAN cluster.

    It is NOT:

    - Evidence confidence
    - Entity Resolution confidence
    - anomaly probability
    - suspiciousness probability
    """

    observation_id: str

    cluster_id: (
        int
        | None
    )

    membership_probability: float

    def __post_init__(
        self,
    ) -> None:

        observation_id = str(
            self.observation_id
        ).strip()

        if not observation_id:

            raise ValueError(
                "observation_id cannot be empty."
            )

        object.__setattr__(
            self,
            "observation_id",
            observation_id,
        )

        if (
            self.cluster_id
            is not None
        ):

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
                    "cluster_id must be None or "
                    "a non-negative integer."
                )

        probability = float(
            self.membership_probability
        )

        if not isfinite(
            probability
        ):

            raise ValueError(
                "membership_probability must "
                "be finite."
            )

        tolerance = 1e-12

        if (
            probability
            <
            -tolerance
            or
            probability
            >
            1.0 + tolerance
        ):

            raise ValueError(
                "membership_probability must "
                "be between 0 and 1."
            )

        probability = min(
            1.0,
            max(
                0.0,
                probability,
            ),
        )

        object.__setattr__(
            self,
            "membership_probability",
            probability,
        )

    @property
    def is_noise(
        self,
    ) -> bool:

        return (
            self.cluster_id
            is None
        )

    @property
    def is_clustered(
        self,
    ) -> bool:

        return (
            self.cluster_id
            is not None
        )


# ==========================================================
# Cluster summary
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HDBSCANClusterSummary:
    """
    Deterministic summary of one HDBSCAN cluster.
    """

    cluster_id: int

    member_ids: tuple[
        str,
        ...,
    ]

    membership_probabilities: tuple[
        float,
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
                "cluster_id must be a "
                "non-negative integer."
            )

        if not isinstance(
            self.member_ids,
            tuple,
        ):

            raise TypeError(
                "member_ids must be tuple."
            )

        if not isinstance(
            self.membership_probabilities,
            tuple,
        ):

            raise TypeError(
                "membership_probabilities "
                "must be tuple."
            )

        if (
            len(
                self.member_ids
            )
            !=
            len(
                self.membership_probabilities
            )
        ):

            raise ValueError(
                "member_ids and "
                "membership_probabilities "
                "must have equal length."
            )

        if not self.member_ids:

            raise ValueError(
                "Cluster cannot be empty."
            )

        normalized_pairs: list[
            tuple[
                str,
                float,
            ]
        ] = []

        seen_ids: set[
            str
        ] = set()

        for (
            member_id,
            probability,
        ) in zip(
            self.member_ids,
            self.membership_probabilities,
            strict=True,
        ):

            normalized_id = str(
                member_id
            ).strip()

            if not normalized_id:

                raise ValueError(
                    "Cluster member ID "
                    "cannot be empty."
                )

            if (
                normalized_id
                in seen_ids
            ):

                raise ValueError(
                    "Duplicate cluster member ID."
                )

            seen_ids.add(
                normalized_id
            )

            probability_float = float(
                probability
            )

            if (
                not isfinite(
                    probability_float
                )
                or
                probability_float < 0.0
                or
                probability_float > 1.0
            ):

                raise ValueError(
                    "Cluster membership "
                    "probabilities must be "
                    "between 0 and 1."
                )

            normalized_pairs.append(
                (
                    normalized_id,
                    probability_float,
                )
            )

        normalized_pairs.sort(
            key=lambda item: item[
                0
            ]
        )

        object.__setattr__(
            self,
            "member_ids",
            tuple(
                member_id
                for (
                    member_id,
                    _
                )
                in normalized_pairs
            ),
        )

        object.__setattr__(
            self,
            "membership_probabilities",
            tuple(
                probability
                for (
                    _,
                    probability
                )
                in normalized_pairs
            ),
        )

    @property
    def size(
        self,
    ) -> int:

        return len(
            self.member_ids
        )

    @property
    def mean_membership_probability(
        self,
    ) -> float:

        return (
            sum(
                self.membership_probabilities
            )
            /
            len(
                self.membership_probabilities
            )
        )

    @property
    def minimum_membership_probability(
        self,
    ) -> float:

        return min(
            self.membership_probabilities
        )

    @property
    def maximum_membership_probability(
        self,
    ) -> float:

        return max(
            self.membership_probabilities
        )


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HDBSCANDiagnostics:
    """
    Execution diagnostics.

    Diagnostic counts describe the numerical clustering
    process only.
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

    clustered_point_count: int

    noise_point_count: int

    mean_clustered_membership_probability: (
        float
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        integer_values = (
            self.sample_count,
            self.feature_count,
            self.variable_feature_count,
            self.cluster_count,
            self.clustered_point_count,
            self.noise_point_count,
        )

        if any(
            (
                not isinstance(
                    value,
                    int,
                )
                or isinstance(
                    value,
                    bool,
                )
                or value < 0
            )
            for value
            in integer_values
        ):

            raise ValueError(
                "Diagnostic counts must be "
                "non-negative integers."
            )

        if (
            self.variable_feature_count
            >
            self.feature_count
        ):

            raise ValueError(
                "variable_feature_count cannot "
                "exceed feature_count."
            )

        if (
            self.clustered_point_count
            +
            self.noise_point_count
            >
            self.sample_count
        ):

            raise ValueError(
                "Assigned diagnostic count cannot "
                "exceed sample_count."
            )

        if not isinstance(
            self.standardized,
            bool,
        ):

            raise TypeError(
                "standardized must be bool."
            )

        if not isinstance(
            self.constant_feature_names,
            tuple,
        ):

            raise TypeError(
                "constant_feature_names "
                "must be tuple."
            )

        if (
            self.mean_clustered_membership_probability
            is not None
        ):

            probability = float(
                self.mean_clustered_membership_probability
            )

            if (
                not isfinite(
                    probability
                )
                or probability < 0.0
                or probability > 1.0
            ):

                raise ValueError(
                    "mean_clustered_membership_probability "
                    "must be between 0 and 1."
                )

            object.__setattr__(
                self,
                "mean_clustered_membership_probability",
                probability,
            )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HDBSCANClusteringResult:
    """
    Complete deterministic HDBSCAN analytical result.
    """

    status: HDBSCANStatus

    config: HDBSCANConfig

    feature_names: tuple[
        str,
        ...,
    ]

    observations: tuple[
        HDBSCANObservationResult,
        ...,
    ]

    clusters: tuple[
        HDBSCANClusterSummary,
        ...,
    ]

    diagnostics: HDBSCANDiagnostics

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.status,
            HDBSCANStatus,
        ):

            raise TypeError(
                "status must be HDBSCANStatus."
            )

        if not isinstance(
            self.config,
            HDBSCANConfig,
        ):

            raise TypeError(
                "config must be HDBSCANConfig."
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
            HDBSCANDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "HDBSCANDiagnostics."
            )

        # ======================================================
        # Observation validation
        # ======================================================

        observation_ids: list[
            str
        ] = []

        for observation in (
            self.observations
        ):

            if not isinstance(
                observation,
                HDBSCANObservationResult,
            ):

                raise TypeError(
                    "observations must contain "
                    "HDBSCANObservationResult."
                )

            observation_ids.append(
                observation.observation_id
            )

        if (
            len(
                set(
                    observation_ids
                )
            )
            !=
            len(
                observation_ids
            )
        ):

            raise ValueError(
                "Duplicate HDBSCAN observation ID."
            )

        if (
            tuple(
                observation_ids
            )
            !=
            tuple(
                sorted(
                    observation_ids
                )
            )
        ):

            raise ValueError(
                "HDBSCAN observations must be "
                "in canonical ID order."
            )

        # ======================================================
        # Cluster validation
        # ======================================================

        cluster_ids: list[
            int
        ] = []

        for cluster in (
            self.clusters
        ):

            if not isinstance(
                cluster,
                HDBSCANClusterSummary,
            ):

                raise TypeError(
                    "clusters must contain "
                    "HDBSCANClusterSummary."
                )

            cluster_ids.append(
                cluster.cluster_id
            )

        if (
            cluster_ids
            !=
            list(
                range(
                    len(
                        cluster_ids
                    )
                )
            )
        ):

            raise ValueError(
                "HDBSCAN cluster IDs must be "
                "canonical contiguous integers."
            )

        expected_members: dict[
            int,
            set[str],
        ] = {}

        for observation in (
            self.observations
        ):

            if (
                observation.cluster_id
                is None
            ):

                continue

            expected_members.setdefault(
                observation.cluster_id,
                set(),
            ).add(
                observation.observation_id
            )

        actual_members = {
            cluster.cluster_id: set(
                cluster.member_ids
            )
            for cluster
            in self.clusters
        }

        if (
            expected_members
            !=
            actual_members
        ):

            raise ValueError(
                "HDBSCAN cluster summaries do not "
                "match observation assignments."
            )

        # ======================================================
        # Diagnostic alignment
        # ======================================================

        if (
            self.diagnostics.sample_count
            !=
            len(
                self.observations
            )
        ):

            if (
                self.status
                ==
                HDBSCANStatus.OK
            ):

                raise ValueError(
                    "Diagnostic sample_count does not "
                    "match observations."
                )

        if (
            self.diagnostics.cluster_count
            !=
            len(
                self.clusters
            )
        ):

            raise ValueError(
                "Diagnostic cluster_count does not "
                "match clusters."
            )

        if (
            self.status
            ==
            HDBSCANStatus.OK
        ):

            clustered_count = sum(
                1
                for observation
                in self.observations
                if observation.is_clustered
            )

            noise_count = sum(
                1
                for observation
                in self.observations
                if observation.is_noise
            )

            if (
                clustered_count
                !=
                self.diagnostics
                .clustered_point_count
            ):

                raise ValueError(
                    "Clustered-point diagnostic "
                    "count mismatch."
                )

            if (
                noise_count
                !=
                self.diagnostics
                .noise_point_count
            ):

                raise ValueError(
                    "Noise-point diagnostic "
                    "count mismatch."
                )

    # ==========================================================
    # Convenience properties
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
    def cluster_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .cluster_count
        )

    @property
    def clustered_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .clustered_point_count
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
    def successful(
        self,
    ) -> bool:

        return (
            self.status
            ==
            HDBSCANStatus.OK
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_observation(
        self,
        observation_id: str,
    ) -> HDBSCANObservationResult:

        normalized_id = str(
            observation_id
        ).strip()

        for observation in (
            self.observations
        ):

            if (
                observation.observation_id
                ==
                normalized_id
            ):

                return observation

        raise KeyError(
            "HDBSCAN observation not found."
        )

    def get_cluster(
        self,
        cluster_id: int,
    ) -> HDBSCANClusterSummary:

        for cluster in (
            self.clusters
        ):

            if (
                cluster.cluster_id
                ==
                cluster_id
            ):

                return cluster

        raise KeyError(
            "HDBSCAN cluster not found."
        )


# ==========================================================
# Service
# ==========================================================


class HDBSCANClusteringService:
    """
    Pure numerical HDBSCAN clustering service.

    No database or application-service dependency.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        matrix: NumericFeatureMatrix,
        config: (
            HDBSCANConfig
            | None
        ) = None,
    ) -> HDBSCANClusteringResult:

        if not isinstance(
            matrix,
            NumericFeatureMatrix,
        ):

            raise TypeError(
                "matrix must be NumericFeatureMatrix."
            )

        config = (
            config
            or HDBSCANConfig()
        )

        if not isinstance(
            config,
            HDBSCANConfig,
        ):

            raise TypeError(
                "config must be HDBSCANConfig."
            )

        canonical_matrix = (
            matrix.canonicalized()
        )

        feature_names = tuple(
            canonical_matrix.feature_names
        )

        sample_count = (
            canonical_matrix.sample_count
        )

        feature_count = (
            canonical_matrix.feature_count
        )

        # ======================================================
        # Empty matrix
        # ======================================================

        if sample_count == 0:

            return self._non_executed_result(
                status=(
                    HDBSCANStatus.EMPTY
                ),
                config=config,
                feature_names=(
                    feature_names
                ),
                sample_count=0,
                feature_count=(
                    feature_count
                ),
                constant_feature_names=(),
                variable_feature_count=0,
            )

        # ======================================================
        # Numerical array
        # ======================================================

        values = np.asarray(
            [
                observation.values
                for observation
                in canonical_matrix.observations
            ],
            dtype=float,
        )

        if values.ndim != 2:

            raise ValueError(
                "NumericFeatureMatrix must produce "
                "a two-dimensional numerical array."
            )

        if (
            values.shape[
                0
            ]
            !=
            sample_count
        ):

            raise ValueError(
                "Numerical sample count mismatch."
            )

        if (
            values.shape[
                1
            ]
            !=
            feature_count
        ):

            raise ValueError(
                "Numerical feature count mismatch."
            )

        if not np.isfinite(
            values
        ).all():

            raise ValueError(
                "HDBSCAN input contains "
                "non-finite values."
            )

        # ======================================================
        # Feature variation diagnostics
        # ======================================================

        if feature_count == 0:

            constant_feature_names: tuple[
                str,
                ...,
            ] = ()

            variable_feature_count = 0

        else:

            constant_mask = np.all(
                values
                ==
                values[
                    0
                ],
                axis=0,
            )

            constant_feature_names = tuple(
                feature_names[
                    index
                ]
                for index
                in range(
                    feature_count
                )
                if bool(
                    constant_mask[
                        index
                    ]
                )
            )

            variable_feature_count = (
                feature_count
                -
                len(
                    constant_feature_names
                )
            )

        # ======================================================
        # Minimum input
        # ======================================================

        required_samples = max(
            config.minimum_input_samples,
            config.min_cluster_size,
        )

        if (
            sample_count
            <
            required_samples
        ):

            return self._non_executed_result(
                status=(
                    HDBSCANStatus
                    .INSUFFICIENT_SAMPLES
                ),
                config=config,
                feature_names=(
                    feature_names
                ),
                sample_count=(
                    sample_count
                ),
                feature_count=(
                    feature_count
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
                variable_feature_count=(
                    variable_feature_count
                ),
            )

        # ======================================================
        # No variation
        # ======================================================

        if (
            variable_feature_count
            ==
            0
        ):

            return self._non_executed_result(
                status=(
                    HDBSCANStatus.NO_VARIATION
                ),
                config=config,
                feature_names=(
                    feature_names
                ),
                sample_count=(
                    sample_count
                ),
                feature_count=(
                    feature_count
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
                variable_feature_count=0,
            )

        # ======================================================
        # Optional standardization
        # ======================================================

        analysis_values = values

        if config.standardize:

            scaler = (
                StandardScaler()
            )

            analysis_values = (
                scaler.fit_transform(
                    values
                )
            )

        # ======================================================
        # HDBSCAN
        # ======================================================

        model = HDBSCAN(
            min_cluster_size=(
                config.min_cluster_size
            ),
            min_samples=(
                config.min_samples
            ),
            cluster_selection_epsilon=(
                config
                .cluster_selection_epsilon
            ),
            max_cluster_size=(
                config.max_cluster_size
            ),
            metric=(
                config.metric
            ),
            alpha=(
                config.alpha
            ),
            algorithm=(
                config.algorithm
            ),
            leaf_size=(
                config.leaf_size
            ),
            n_jobs=(
                config.n_jobs
            ),
            cluster_selection_method=(
                config
                .cluster_selection_method
            ),
            allow_single_cluster=(
                config.allow_single_cluster
            ),
            store_centers=None,
            copy=(
                config.copy
            ),
        )

        model.fit(
            analysis_values
        )

        raw_labels = np.asarray(
            model.labels_,
            dtype=int,
        )

        probabilities = np.asarray(
            model.probabilities_,
            dtype=float,
        )

        if (
            raw_labels.shape
            !=
            (
                sample_count,
            )
        ):

            raise RuntimeError(
                "HDBSCAN labels_ shape mismatch."
            )

        if (
            probabilities.shape
            !=
            (
                sample_count,
            )
        ):

            raise RuntimeError(
                "HDBSCAN probabilities_ "
                "shape mismatch."
            )

        if not np.isfinite(
            probabilities
        ).all():

            raise RuntimeError(
                "HDBSCAN returned non-finite "
                "membership probabilities."
            )

        # ======================================================
        # Canonical cluster IDs
        # ======================================================

        cluster_id_map = (
            self._canonical_cluster_id_map(
                labels=raw_labels,
                observation_ids=(
                    canonical_matrix
                    .observation_ids
                ),
            )
        )

        # ======================================================
        # Observation results
        # ======================================================

        observations: list[
            HDBSCANObservationResult
        ] = []

        for (
            observation,
            raw_label,
            probability,
        ) in zip(
            canonical_matrix.observations,
            raw_labels,
            probabilities,
            strict=True,
        ):

            label = int(
                raw_label
            )

            cluster_id = (
                None
                if label == -1
                else cluster_id_map[
                    label
                ]
            )

            probability_value = float(
                probability
            )

            tolerance = 1e-12

            if (
                probability_value
                <
                -tolerance
                or
                probability_value
                >
                1.0 + tolerance
            ):

                raise RuntimeError(
                    "HDBSCAN returned membership "
                    "probability outside [0, 1]."
                )

            probability_value = min(
                1.0,
                max(
                    0.0,
                    probability_value,
                ),
            )

            observations.append(
                HDBSCANObservationResult(
                    observation_id=(
                        observation
                        .observation_id
                    ),
                    cluster_id=(
                        cluster_id
                    ),
                    membership_probability=(
                        probability_value
                    ),
                )
            )

        observation_tuple = tuple(
            observations
        )

        # ======================================================
        # Cluster summaries
        # ======================================================

        clusters = (
            self._build_cluster_summaries(
                observation_tuple
            )
        )

        clustered_probabilities = [
            observation
            .membership_probability
            for observation
            in observation_tuple
            if observation.is_clustered
        ]

        clustered_point_count = len(
            clustered_probabilities
        )

        noise_point_count = (
            sample_count
            -
            clustered_point_count
        )

        mean_probability = (
            (
                sum(
                    clustered_probabilities
                )
                /
                len(
                    clustered_probabilities
                )
            )
            if clustered_probabilities
            else None
        )

        diagnostics = (
            HDBSCANDiagnostics(
                sample_count=(
                    sample_count
                ),
                feature_count=(
                    feature_count
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
                variable_feature_count=(
                    variable_feature_count
                ),
                standardized=(
                    config.standardize
                ),
                cluster_count=(
                    len(
                        clusters
                    )
                ),
                clustered_point_count=(
                    clustered_point_count
                ),
                noise_point_count=(
                    noise_point_count
                ),
                mean_clustered_membership_probability=(
                    mean_probability
                ),
            )
        )

        return (
            HDBSCANClusteringResult(
                status=(
                    HDBSCANStatus.OK
                ),
                config=config,
                feature_names=(
                    feature_names
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
        *,
        labels: np.ndarray,
        observation_ids: tuple[
            str,
            ...,
        ],
    ) -> dict[
        int,
        int,
    ]:
        """
        Normalize arbitrary model cluster numbers.

        Cluster IDs are ordered by their canonical member-ID
        tuples rather than sklearn's raw label numbering.
        """

        members_by_raw_label: dict[
            int,
            list[str],
        ] = {}

        for (
            observation_id,
            raw_label,
        ) in zip(
            observation_ids,
            labels,
            strict=True,
        ):

            label = int(
                raw_label
            )

            if label == -1:

                continue

            members_by_raw_label.setdefault(
                label,
                [],
            ).append(
                str(
                    observation_id
                )
            )

        ordered_raw_labels = sorted(
            members_by_raw_label,
            key=lambda raw_label: tuple(
                sorted(
                    members_by_raw_label[
                        raw_label
                    ]
                )
            ),
        )

        return {
            raw_label: canonical_id
            for (
                canonical_id,
                raw_label,
            )
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
            HDBSCANObservationResult,
            ...,
        ],
    ) -> tuple[
        HDBSCANClusterSummary,
        ...,
    ]:

        grouped: dict[
            int,
            list[
                HDBSCANObservationResult
            ],
        ] = {}

        for observation in (
            observations
        ):

            if (
                observation.cluster_id
                is None
            ):

                continue

            grouped.setdefault(
                observation.cluster_id,
                [],
            ).append(
                observation
            )

        summaries: list[
            HDBSCANClusterSummary
        ] = []

        for cluster_id in sorted(
            grouped
        ):

            members = sorted(
                grouped[
                    cluster_id
                ],
                key=lambda observation: (
                    observation
                    .observation_id
                ),
            )

            summaries.append(
                HDBSCANClusterSummary(
                    cluster_id=(
                        cluster_id
                    ),
                    member_ids=tuple(
                        observation
                        .observation_id
                        for observation
                        in members
                    ),
                    membership_probabilities=tuple(
                        observation
                        .membership_probability
                        for observation
                        in members
                    ),
                )
            )

        return tuple(
            summaries
        )

    # ==========================================================
    # Non-executed result
    # ==========================================================

    @staticmethod
    def _non_executed_result(
        *,
        status: HDBSCANStatus,
        config: HDBSCANConfig,
        feature_names: tuple[
            str,
            ...,
        ],
        sample_count: int,
        feature_count: int,
        constant_feature_names: tuple[
            str,
            ...,
        ],
        variable_feature_count: int,
    ) -> HDBSCANClusteringResult:

        return (
            HDBSCANClusteringResult(
                status=status,
                config=config,
                feature_names=(
                    feature_names
                ),
                observations=(),
                clusters=(),
                diagnostics=(
                    HDBSCANDiagnostics(
                        sample_count=(
                            sample_count
                        ),
                        feature_count=(
                            feature_count
                        ),
                        constant_feature_names=(
                            constant_feature_names
                        ),
                        variable_feature_count=(
                            variable_feature_count
                        ),
                        standardized=False,
                        cluster_count=0,
                        clustered_point_count=0,
                        noise_point_count=0,
                        mean_clustered_membership_probability=None,
                    )
                ),
            )
        )