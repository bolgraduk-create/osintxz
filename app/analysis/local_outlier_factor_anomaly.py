"""
Local Outlier Factor anomaly analysis.

Phase 5.2.

Pipeline:

NumericFeatureMatrix
    ↓
validation
    ↓
deterministic row ordering
    ↓
optional feature standardization
    ↓
LocalOutlierFactor
    ↓
negative_outlier_factor_
fit_predict labels
offset threshold
    ↓
LocalOutlierFactorResult

Scoring semantics:

negative_outlier_factor:

    Native sklearn negative_outlier_factor_ value.

    Higher values are more normal.
    Inliers typically have values near -1.
    Lower values are more locally abnormal.

local_outlier_factor:

    Convenience transformation:

        local_outlier_factor
        =
        -negative_outlier_factor

    Higher values therefore mean stronger local
    density deviation.

threshold_margin:

        negative_outlier_factor - offset

    Negative:
        classified as outlier.

    Non-negative:
        classified as inlier.

Important:

Local Outlier Factor
    != suspicious activity
    != malicious activity
    != evidence
    != relationship
    != identity signal
    != causation

This module does NOT:

- query the database
- write to the database
- create Evidence
- create Relationships
- merge Entities
- infer intent
- infer criminality
- create investigation conclusions
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import (
    isclose,
    isfinite,
)

import numpy as np

from sklearn.neighbors import (
    LocalOutlierFactor,
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


class LocalOutlierFactorStatus(
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
# Label
# ==========================================================


class LocalOutlierFactorLabel(
    str,
    Enum,
):
    """
    Native LOF outlier-detection label.
    """

    INLIER = "inlier"

    OUTLIER = "outlier"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LocalOutlierFactorConfig:
    """
    LOF configuration.

    n_neighbors:

        Requested number of nearest neighbors.

        If fewer samples exist, the effective value is:

            min(
                n_neighbors,
                sample_count - 1
            )

        The effective value is always exposed in the
        result rather than silently hidden.

    contamination:

        "auto" or expected outlier fraction in:

            (0, 0.5]

    standardize:

        Standardize each feature before calculating
        distances.

        Recommended by default because LOF is
        distance-based.

    metric:

        sklearn neighbor-distance metric.

        Phase 5.2 deliberately defaults to Minkowski.

    p:

        Minkowski power.

        p=2 gives Euclidean distance.

    minimum_samples:

        Application-level safety threshold below which
        LOF is not fitted.
    """

    n_neighbors: int = 20

    contamination: (
        str
        | float
    ) = "auto"

    standardize: bool = True

    metric: str = "minkowski"

    p: float = 2.0

    algorithm: str = "auto"

    leaf_size: int = 30

    n_jobs: (
        int
        | None
    ) = 1

    minimum_samples: int = 5

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # Neighbors
        # ======================================================

        if (
            not isinstance(
                self.n_neighbors,
                int,
            )
            or isinstance(
                self.n_neighbors,
                bool,
            )
            or self.n_neighbors < 2
        ):

            raise ValueError(
                "n_neighbors must be "
                "an integer >= 2."
            )

        # ======================================================
        # Contamination
        # ======================================================

        contamination = (
            self.contamination
        )

        if isinstance(
            contamination,
            str,
        ):

            if contamination != "auto":

                raise ValueError(
                    "contamination string must "
                    "be 'auto'."
                )

        else:

            if isinstance(
                contamination,
                bool,
            ):

                raise TypeError(
                    "contamination cannot be bool."
                )

            contamination = float(
                contamination
            )

            if (
                not isfinite(
                    contamination
                )
                or not (
                    0.0
                    <
                    contamination
                    <=
                    0.5
                )
            ):

                raise ValueError(
                    "Float contamination must "
                    "be in (0, 0.5]."
                )

            object.__setattr__(
                self,
                "contamination",
                contamination,
            )

        # ======================================================
        # Standardization
        # ======================================================

        if not isinstance(
            self.standardize,
            bool,
        ):

            raise TypeError(
                "standardize must be bool."
            )

        # ======================================================
        # Metric
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

        object.__setattr__(
            self,
            "metric",
            self.metric.strip(),
        )

        # ======================================================
        # Minkowski power
        # ======================================================

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
        # Algorithm
        # ======================================================

        if self.algorithm not in (
            "auto",
            "ball_tree",
            "kd_tree",
            "brute",
        ):

            raise ValueError(
                "Unsupported neighbor algorithm."
            )

        # ======================================================
        # Leaf size
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
        # Jobs
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
        # Minimum samples
        # ======================================================

        if (
            not isinstance(
                self.minimum_samples,
                int,
            )
            or isinstance(
                self.minimum_samples,
                bool,
            )
            or self.minimum_samples < 3
        ):

            raise ValueError(
                "minimum_samples must be "
                "an integer >= 3."
            )


# ==========================================================
# One observation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LocalOutlierFactorObservationResult:
    """
    LOF output for one observation.
    """

    observation_id: str

    negative_outlier_factor: float

    local_outlier_factor: float

    threshold_margin: float

    label: LocalOutlierFactorLabel

    anomaly_rank: int

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

        for field_name in (
            "negative_outlier_factor",
            "local_outlier_factor",
            "threshold_margin",
        ):

            value = float(
                getattr(
                    self,
                    field_name,
                )
            )

            if not isfinite(
                value
            ):

                raise ValueError(
                    f"{field_name} must be finite."
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        if not isclose(
            self.local_outlier_factor,
            -self.negative_outlier_factor,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):

            raise ValueError(
                "local_outlier_factor must equal "
                "-negative_outlier_factor."
            )

        if not isinstance(
            self.label,
            LocalOutlierFactorLabel,
        ):

            raise TypeError(
                "label must be "
                "LocalOutlierFactorLabel."
            )

        if (
            not isinstance(
                self.anomaly_rank,
                int,
            )
            or self.anomaly_rank < 1
        ):

            raise ValueError(
                "anomaly_rank must be >= 1."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def is_outlier(
        self,
    ) -> bool:

        return (
            self.label
            ==
            LocalOutlierFactorLabel.OUTLIER
        )


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LocalOutlierFactorDiagnostics:
    """
    Non-interpretive LOF diagnostics.
    """

    sample_count: int

    feature_count: int

    constant_feature_names: tuple[
        str,
        ...,
    ]

    variable_feature_count: int

    standardized: bool

    requested_n_neighbors: int

    effective_n_neighbors: (
        int
        | None
    )

    inlier_count: int

    outlier_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "sample_count",
            "feature_count",
            "variable_feature_count",
            "requested_n_neighbors",
            "inlier_count",
            "outlier_count",
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
            self.requested_n_neighbors
            <
            2
        ):

            raise ValueError(
                "requested_n_neighbors "
                "must be >= 2."
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

        if (
            self.effective_n_neighbors
            is not None
        ):

            if (
                not isinstance(
                    self.effective_n_neighbors,
                    int,
                )
                or
                self.effective_n_neighbors
                <
                1
            ):

                raise ValueError(
                    "effective_n_neighbors must "
                    "be positive or None."
                )

            if (
                self.sample_count > 0
                and
                self.effective_n_neighbors
                >=
                self.sample_count
            ):

                raise ValueError(
                    "effective_n_neighbors must "
                    "be smaller than sample_count."
                )

        if (
            self.inlier_count
            +
            self.outlier_count
            >
            self.sample_count
        ):

            raise ValueError(
                "LOF label count cannot exceed "
                "sample_count."
            )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class LocalOutlierFactorResult:
    """
    Complete Phase 5.2 LOF result.
    """

    status: LocalOutlierFactorStatus

    config: LocalOutlierFactorConfig

    feature_names: tuple[
        str,
        ...,
    ]

    observations: tuple[
        LocalOutlierFactorObservationResult,
        ...,
    ]

    diagnostics: LocalOutlierFactorDiagnostics

    offset: (
        float
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.status,
            LocalOutlierFactorStatus,
        ):

            raise TypeError(
                "status must be "
                "LocalOutlierFactorStatus."
            )

        if not isinstance(
            self.config,
            LocalOutlierFactorConfig,
        ):

            raise TypeError(
                "config must be "
                "LocalOutlierFactorConfig."
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
            self.diagnostics,
            LocalOutlierFactorDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "LocalOutlierFactorDiagnostics."
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
            LocalOutlierFactorStatus.OK
        ):

            if (
                len(
                    self.observations
                )
                !=
                self.diagnostics.sample_count
            ):

                raise ValueError(
                    "Successful LOF result must "
                    "contain one result per sample."
                )

            if self.offset is None:

                raise ValueError(
                    "Successful LOF result "
                    "requires offset."
                )

            offset = float(
                self.offset
            )

            if not isfinite(
                offset
            ):

                raise ValueError(
                    "LOF offset must be finite."
                )

            object.__setattr__(
                self,
                "offset",
                offset,
            )

            if (
                self.diagnostics
                .effective_n_neighbors
                is None
            ):

                raise ValueError(
                    "Successful LOF result requires "
                    "effective_n_neighbors."
                )

            expected_ranks = set(
                range(
                    1,
                    len(
                        self.observations
                    )
                    +
                    1,
                )
            )

            actual_ranks = {
                item.anomaly_rank
                for item
                in self.observations
            }

            if (
                expected_ranks
                !=
                actual_ranks
            ):

                raise ValueError(
                    "LOF ranks must form "
                    "1..N without duplicates."
                )

            actual_inliers = sum(
                1
                for item
                in self.observations
                if not item.is_outlier
            )

            actual_outliers = sum(
                1
                for item
                in self.observations
                if item.is_outlier
            )

            if (
                actual_inliers
                !=
                self.diagnostics.inlier_count
            ):

                raise ValueError(
                    "LOF inlier count mismatch."
                )

            if (
                actual_outliers
                !=
                self.diagnostics.outlier_count
            ):

                raise ValueError(
                    "LOF outlier count mismatch."
                )

        else:

            if self.observations:

                raise ValueError(
                    "Unfitted LOF result cannot "
                    "contain scores."
                )

            if self.offset is not None:

                raise ValueError(
                    "Unfitted LOF result cannot "
                    "contain offset."
                )

            if (
                self.diagnostics
                .effective_n_neighbors
                is not None
            ):

                raise ValueError(
                    "Unfitted LOF result cannot "
                    "contain effective neighbors."
                )

            if (
                self.diagnostics.inlier_count
                !=
                0
                or
                self.diagnostics.outlier_count
                !=
                0
            ):

                raise ValueError(
                    "Unfitted LOF result cannot "
                    "contain labels."
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
    def outlier_count(
        self,
    ) -> int:

        return (
            self.diagnostics
            .outlier_count
        )

    @property
    def is_fitted(
        self,
    ) -> bool:

        return (
            self.status
            ==
            LocalOutlierFactorStatus.OK
        )

    @property
    def outliers(
        self,
    ) -> tuple[
        LocalOutlierFactorObservationResult,
        ...,
    ]:

        return tuple(
            sorted(
                (
                    item
                    for item
                    in self.observations
                    if item.is_outlier
                ),
                key=lambda item: (
                    item.anomaly_rank
                ),
            )
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top_anomalies(
        self,
        limit: int = 10,
    ) -> tuple[
        LocalOutlierFactorObservationResult,
        ...,
    ]:

        if (
            not isinstance(
                limit,
                int,
            )
            or isinstance(
                limit,
                bool,
            )
            or limit < 0
        ):

            raise ValueError(
                "limit must be a "
                "non-negative integer."
            )

        ordered = sorted(
            self.observations,
            key=lambda item: (
                item.anomaly_rank
            ),
        )

        return tuple(
            ordered[
                :limit
            ]
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_observation(
        self,
        observation_id: str,
    ) -> LocalOutlierFactorObservationResult:

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
            "LOF observation not found."
        )


# ==========================================================
# Service
# ==========================================================


class LocalOutlierFactorAnomalyService:
    """
    Pure Local Outlier Factor analytical service.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        matrix: NumericFeatureMatrix,
        config: (
            LocalOutlierFactorConfig
            | None
        ) = None,
    ) -> LocalOutlierFactorResult:
        """
        Fit LOF in outlier-detection mode against the
        supplied observations.

        No persistence is performed.
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
            LocalOutlierFactorConfig()
        )

        if not isinstance(
            config,
            LocalOutlierFactorConfig,
        ):

            raise TypeError(
                "config must be "
                "LocalOutlierFactorConfig."
            )

        # ======================================================
        # Canonical row order
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
                    LocalOutlierFactorStatus.EMPTY
                ),
                constant_feature_names=(),
            )

        # ======================================================
        # Numeric matrix
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
        # Insufficient samples
        # ======================================================

        if (
            matrix.sample_count
            <
            config.minimum_samples
        ):

            return self._unfitted_result(
                matrix,
                config,
                status=(
                    LocalOutlierFactorStatus
                    .INSUFFICIENT_SAMPLES
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # No variation
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
                    LocalOutlierFactorStatus
                    .NO_VARIATION
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # Effective neighborhood
        #
        # sklearn can reduce an oversized n_neighbors
        # automatically and emit a warning.
        #
        # We do it explicitly instead so the production
        # result records the actual neighborhood size.
        # ======================================================

        effective_n_neighbors = min(
            config.n_neighbors,
            (
                matrix.sample_count
                -
                1
            ),
        )

        if effective_n_neighbors < 1:

            raise RuntimeError(
                "LOF requires at least one neighbor."
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
        # Fit / predict
        #
        # novelty=False is intentionally used.
        #
        # We are detecting outliers inside the supplied
        # investigation matrix rather than evaluating new
        # unseen observations.
        # ======================================================

        model = LocalOutlierFactor(
            n_neighbors=(
                effective_n_neighbors
            ),
            algorithm=(
                config.algorithm
            ),
            leaf_size=(
                config.leaf_size
            ),
            metric=(
                config.metric
            ),
            p=(
                config.p
            ),
            contamination=(
                config.contamination
            ),
            novelty=False,
            n_jobs=(
                config.n_jobs
            ),
        )

        predictions = (
            model.fit_predict(
                model_values
            )
        )

        negative_factors = (
            model
            .negative_outlier_factor_
        )

        offset = float(
            model.offset_
        )

        fitted_neighbors = int(
            model.n_neighbors_
        )

        if (
            fitted_neighbors
            !=
            effective_n_neighbors
        ):

            raise RuntimeError(
                "Unexpected LOF neighborhood size."
            )

        # ======================================================
        # Rank
        #
        # Lower negative_outlier_factor_
        # =
        # larger positive LOF
        # =
        # more locally abnormal.
        # ======================================================

        lof_scores = [
            -float(
                value
            )
            for value
            in negative_factors
        ]

        ranking_indices = sorted(
            range(
                matrix.sample_count
            ),
            key=lambda index: (
                -lof_scores[
                    index
                ],
                matrix
                .observations[
                    index
                ]
                .observation_id,
            ),
        )

        ranks = {
            observation_index:
                rank
            for rank, observation_index
            in enumerate(
                ranking_indices,
                start=1,
            )
        }

        # ======================================================
        # Observation results
        # ======================================================

        results: list[
            LocalOutlierFactorObservationResult
        ] = []

        for index, observation in enumerate(
            matrix.observations
        ):

            negative_factor = float(
                negative_factors[
                    index
                ]
            )

            prediction = int(
                predictions[
                    index
                ]
            )

            if prediction == -1:

                label = (
                    LocalOutlierFactorLabel.OUTLIER
                )

            elif prediction == 1:

                label = (
                    LocalOutlierFactorLabel.INLIER
                )

            else:

                raise RuntimeError(
                    "Unexpected LOF prediction label."
                )

            threshold_margin = (
                negative_factor
                -
                offset
            )

            # ==================================================
            # sklearn label / threshold consistency
            # ==================================================

            if (
                negative_factor
                <
                offset
                and
                label
                !=
                LocalOutlierFactorLabel.OUTLIER
            ):

                raise RuntimeError(
                    "LOF threshold / label mismatch."
                )

            if (
                negative_factor
                >=
                offset
                and
                label
                !=
                LocalOutlierFactorLabel.INLIER
            ):

                raise RuntimeError(
                    "LOF threshold / label mismatch."
                )

            results.append(
                LocalOutlierFactorObservationResult(
                    observation_id=(
                        observation
                        .observation_id
                    ),
                    negative_outlier_factor=(
                        negative_factor
                    ),
                    local_outlier_factor=(
                        -negative_factor
                    ),
                    threshold_margin=(
                        threshold_margin
                    ),
                    label=label,
                    anomaly_rank=(
                        ranks[
                            index
                        ]
                    ),
                )
            )

        result_tuple = tuple(
            results
        )

        inlier_count = sum(
            1
            for item
            in result_tuple
            if not item.is_outlier
        )

        outlier_count = sum(
            1
            for item
            in result_tuple
            if item.is_outlier
        )

        diagnostics = (
            LocalOutlierFactorDiagnostics(
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
                requested_n_neighbors=(
                    config.n_neighbors
                ),
                effective_n_neighbors=(
                    effective_n_neighbors
                ),
                inlier_count=(
                    inlier_count
                ),
                outlier_count=(
                    outlier_count
                ),
            )
        )

        return (
            LocalOutlierFactorResult(
                status=(
                    LocalOutlierFactorStatus.OK
                ),
                config=config,
                feature_names=(
                    matrix.feature_names
                ),
                observations=(
                    result_tuple
                ),
                diagnostics=(
                    diagnostics
                ),
                offset=offset,
            )
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
        config: LocalOutlierFactorConfig,
        *,
        status: LocalOutlierFactorStatus,
        constant_feature_names: tuple[
            str,
            ...,
        ],
    ) -> LocalOutlierFactorResult:

        diagnostics = (
            LocalOutlierFactorDiagnostics(
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
                requested_n_neighbors=(
                    config.n_neighbors
                ),
                effective_n_neighbors=None,
                inlier_count=0,
                outlier_count=0,
            )
        )

        return (
            LocalOutlierFactorResult(
                status=status,
                config=config,
                feature_names=(
                    matrix.feature_names
                ),
                observations=(),
                diagnostics=(
                    diagnostics
                ),
                offset=None,
            )
        )