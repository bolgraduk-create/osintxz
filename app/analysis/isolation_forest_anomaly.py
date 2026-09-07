"""
Isolation Forest anomaly analysis.

Phase 5.1.

Pipeline:

NumericFeatureMatrix
    ↓
validation
    ↓
deterministic row ordering
    ↓
IsolationForest
    ↓
score_samples
decision_function
predict
    ↓
IsolationForestResult

Scoring semantics:

raw_score:
    Native sklearn score_samples() value.

    Lower values are more abnormal.

decision_score:
    Native sklearn decision_function() value.

    Negative values are classified as outliers.

anomaly_score:
    Convenience transformation:

        anomaly_score = -raw_score

    Higher values therefore mean "more unusual".

Important:

Isolation Forest anomaly
    != suspicious person
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
- infer criminality
- create an investigation conclusion
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import (
    isclose,
    isfinite,
)

import numpy as np

from sklearn.ensemble import (
    IsolationForest,
)

from app.analysis.anomaly_contracts import (
    NumericFeatureMatrix,
)


# ==========================================================
# Analysis status
# ==========================================================


class IsolationForestStatus(
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
# Observation label
# ==========================================================


class IsolationForestLabel(
    str,
    Enum,
):
    """
    Native Isolation Forest classification.
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
class IsolationForestConfig:
    """
    Isolation Forest configuration.

    n_estimators:

        Number of isolation trees.

    contamination:

        "auto" or expected outlier fraction in:

            (0, 0.5]

    max_samples:

        Number/fraction of observations sampled by each
        isolation tree.

    max_features:

        Number/fraction of features sampled by each tree.

    random_state:

        Explicit integer seed for deterministic execution.

    minimum_samples:

        Analysis is not fitted below this number of
        observations.

        This is our application safety threshold rather
        than a sklearn requirement.
    """

    n_estimators: int = 200

    contamination: (
        str
        | float
    ) = "auto"

    max_samples: (
        str
        | int
        | float
    ) = "auto"

    max_features: (
        int
        | float
    ) = 1.0

    bootstrap: bool = False

    random_state: int = 42

    n_jobs: (
        int
        | None
    ) = 1

    minimum_samples: int = 5

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # Trees
        # ======================================================

        if (
            not isinstance(
                self.n_estimators,
                int,
            )
            or isinstance(
                self.n_estimators,
                bool,
            )
            or self.n_estimators < 1
        ):

            raise ValueError(
                "n_estimators must be "
                "a positive integer."
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
        # max_samples
        # ======================================================

        max_samples = (
            self.max_samples
        )

        if isinstance(
            max_samples,
            str,
        ):

            if max_samples != "auto":

                raise ValueError(
                    "max_samples string must "
                    "be 'auto'."
                )

        elif isinstance(
            max_samples,
            bool,
        ):

            raise TypeError(
                "max_samples cannot be bool."
            )

        elif isinstance(
            max_samples,
            int,
        ):

            if max_samples < 1:

                raise ValueError(
                    "Integer max_samples must "
                    "be >= 1."
                )

        else:

            normalized_max_samples = float(
                max_samples
            )

            if (
                not isfinite(
                    normalized_max_samples
                )
                or not (
                    0.0
                    <
                    normalized_max_samples
                    <=
                    1.0
                )
            ):

                raise ValueError(
                    "Float max_samples must "
                    "be in (0, 1]."
                )

            object.__setattr__(
                self,
                "max_samples",
                normalized_max_samples,
            )

        # ======================================================
        # max_features
        # ======================================================

        max_features = (
            self.max_features
        )

        if isinstance(
            max_features,
            bool,
        ):

            raise TypeError(
                "max_features cannot be bool."
            )

        if isinstance(
            max_features,
            int,
        ):

            if max_features < 1:

                raise ValueError(
                    "Integer max_features must "
                    "be >= 1."
                )

        else:

            normalized_max_features = float(
                max_features
            )

            if (
                not isfinite(
                    normalized_max_features
                )
                or not (
                    0.0
                    <
                    normalized_max_features
                    <=
                    1.0
                )
            ):

                raise ValueError(
                    "Float max_features must "
                    "be in (0, 1]."
                )

            object.__setattr__(
                self,
                "max_features",
                normalized_max_features,
            )

        # ======================================================
        # Bootstrap
        # ======================================================

        if not isinstance(
            self.bootstrap,
            bool,
        ):

            raise TypeError(
                "bootstrap must be bool."
            )

        # ======================================================
        # Random state
        # ======================================================

        if (
            not isinstance(
                self.random_state,
                int,
            )
            or isinstance(
                self.random_state,
                bool,
            )
        ):

            raise TypeError(
                "random_state must be an integer."
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
            or self.minimum_samples < 2
        ):

            raise ValueError(
                "minimum_samples must be "
                "an integer >= 2."
            )


# ==========================================================
# One observation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class IsolationForestObservationResult:
    """
    Isolation Forest output for one observation.
    """

    observation_id: str

    raw_score: float

    decision_score: float

    anomaly_score: float

    label: IsolationForestLabel

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
            "raw_score",
            "decision_score",
            "anomaly_score",
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
            self.anomaly_score,
            -self.raw_score,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):

            raise ValueError(
                "anomaly_score must equal "
                "-raw_score."
            )

        if not isinstance(
            self.label,
            IsolationForestLabel,
        ):

            raise TypeError(
                "label must be "
                "IsolationForestLabel."
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

    @property
    def is_outlier(
        self,
    ) -> bool:

        return (
            self.label
            ==
            IsolationForestLabel.OUTLIER
        )


# ==========================================================
# Diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class IsolationForestDiagnostics:
    """
    Non-interpretive diagnostics about the fitted data.
    """

    sample_count: int

    feature_count: int

    constant_feature_names: tuple[
        str,
        ...,
    ]

    variable_feature_count: int

    inlier_count: int

    outlier_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "sample_count",
            "feature_count",
            "variable_feature_count",
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

        if not isinstance(
            self.constant_feature_names,
            tuple,
        ):

            raise TypeError(
                "constant_feature_names must "
                "be a tuple."
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
            self.inlier_count
            +
            self.outlier_count
            >
            self.sample_count
        ):

            raise ValueError(
                "Label count cannot exceed "
                "sample_count."
            )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class IsolationForestResult:
    """
    Complete Phase 5.1 Isolation Forest result.
    """

    status: IsolationForestStatus

    config: IsolationForestConfig

    feature_names: tuple[
        str,
        ...,
    ]

    observations: tuple[
        IsolationForestObservationResult,
        ...,
    ]

    diagnostics: IsolationForestDiagnostics

    offset: (
        float
        | None
    )

    fitted_max_samples: (
        int
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.status,
            IsolationForestStatus,
        ):

            raise TypeError(
                "status must be "
                "IsolationForestStatus."
            )

        if not isinstance(
            self.config,
            IsolationForestConfig,
        ):

            raise TypeError(
                "config must be "
                "IsolationForestConfig."
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
            IsolationForestDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "IsolationForestDiagnostics."
            )

        if (
            len(
                self.feature_names
            )
            !=
            self.diagnostics.feature_count
        ):

            raise ValueError(
                "feature_names / diagnostics "
                "feature count mismatch."
            )

        if (
            self.status
            ==
            IsolationForestStatus.OK
        ):

            if (
                len(
                    self.observations
                )
                !=
                self.diagnostics.sample_count
            ):

                raise ValueError(
                    "Successful result must contain "
                    "one score per sample."
                )

            if self.offset is None:

                raise ValueError(
                    "Successful result requires offset."
                )

            if self.fitted_max_samples is None:

                raise ValueError(
                    "Successful result requires "
                    "fitted_max_samples."
                )

            offset = float(
                self.offset
            )

            if not isfinite(
                offset
            ):

                raise ValueError(
                    "offset must be finite."
                )

            object.__setattr__(
                self,
                "offset",
                offset,
            )

            if (
                not isinstance(
                    self.fitted_max_samples,
                    int,
                )
                or self.fitted_max_samples < 1
            ):

                raise ValueError(
                    "fitted_max_samples must "
                    "be positive."
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
                actual_ranks
                !=
                expected_ranks
            ):

                raise ValueError(
                    "Anomaly ranks must form "
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
                    "Inlier count mismatch."
                )

            if (
                actual_outliers
                !=
                self.diagnostics.outlier_count
            ):

                raise ValueError(
                    "Outlier count mismatch."
                )

        else:

            if self.observations:

                raise ValueError(
                    "Non-fitted result must not "
                    "contain scored observations."
                )

            if self.offset is not None:

                raise ValueError(
                    "Non-fitted result cannot "
                    "contain offset."
                )

            if (
                self.fitted_max_samples
                is not None
            ):

                raise ValueError(
                    "Non-fitted result cannot contain "
                    "fitted_max_samples."
                )

            if (
                self.diagnostics.inlier_count != 0
                or
                self.diagnostics.outlier_count != 0
            ):

                raise ValueError(
                    "Non-fitted result cannot "
                    "contain model labels."
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
            IsolationForestStatus.OK
        )

    @property
    def outliers(
        self,
    ) -> tuple[
        IsolationForestObservationResult,
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

    def top_anomalies(
        self,
        limit: int = 10,
    ) -> tuple[
        IsolationForestObservationResult,
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

    def get_observation(
        self,
        observation_id: str,
    ) -> IsolationForestObservationResult:

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
            "Isolation Forest observation "
            "not found."
        )


# ==========================================================
# Service
# ==========================================================


class IsolationForestAnomalyService:
    """
    Pure Isolation Forest analytical service.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        matrix: NumericFeatureMatrix,
        config: (
            IsolationForestConfig
            | None
        ) = None,
    ) -> IsolationForestResult:
        """
        Fit Isolation Forest and score all observations.

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
            IsolationForestConfig()
        )

        if not isinstance(
            config,
            IsolationForestConfig,
        ):

            raise TypeError(
                "config must be "
                "IsolationForestConfig."
            )

        matrix = (
            matrix.canonicalized()
        )

        self._validate_config_for_matrix(
            matrix,
            config,
        )

        # ======================================================
        # Empty
        # ======================================================

        if matrix.sample_count == 0:

            return self._unfitted_result(
                matrix,
                config,
                status=(
                    IsolationForestStatus.EMPTY
                ),
                constant_feature_names=(),
            )

        # ======================================================
        # Matrix
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
        # Insufficient observations
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
                    IsolationForestStatus
                    .INSUFFICIENT_SAMPLES
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # No discriminative numerical variation
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
                    IsolationForestStatus
                    .NO_VARIATION
                ),
                constant_feature_names=(
                    constant_feature_names
                ),
            )

        # ======================================================
        # Fit
        # ======================================================

        model = IsolationForest(
            n_estimators=(
                config.n_estimators
            ),
            contamination=(
                config.contamination
            ),
            max_samples=(
                config.max_samples
            ),
            max_features=(
                config.max_features
            ),
            bootstrap=(
                config.bootstrap
            ),
            random_state=(
                config.random_state
            ),
            n_jobs=(
                config.n_jobs
            ),
        )

        model.fit(
            values
        )

        raw_scores = (
            model.score_samples(
                values
            )
        )

        decision_scores = (
            model.decision_function(
                values
            )
        )

        predictions = (
            model.predict(
                values
            )
        )

        offset = float(
            model.offset_
        )

        # ======================================================
        # Verify sklearn score relationship
        # ======================================================

        for (
            raw_score,
            decision_score,
        ) in zip(
            raw_scores,
            decision_scores,
        ):

            expected_decision = (
                float(
                    raw_score
                )
                -
                offset
            )

            if not isclose(
                float(
                    decision_score
                ),
                expected_decision,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):

                raise RuntimeError(
                    "Unexpected Isolation Forest "
                    "score relationship."
                )

        # ======================================================
        # Rank
        #
        # Higher anomaly_score = more anomalous.
        #
        # Equal scores are resolved deterministically by
        # observation ID.
        # ======================================================

        anomaly_scores = [
            -float(
                raw_score
            )
            for raw_score
            in raw_scores
        ]

        ranking_indices = sorted(
            range(
                matrix.sample_count
            ),
            key=lambda index: (
                -anomaly_scores[
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
        # Build results
        # ======================================================

        observation_results: list[
            IsolationForestObservationResult
        ] = []

        for index, observation in enumerate(
            matrix.observations
        ):

            prediction = int(
                predictions[
                    index
                ]
            )

            if prediction == -1:

                label = (
                    IsolationForestLabel.OUTLIER
                )

            elif prediction == 1:

                label = (
                    IsolationForestLabel.INLIER
                )

            else:

                raise RuntimeError(
                    "Unexpected Isolation Forest "
                    "prediction label."
                )

            observation_results.append(
                IsolationForestObservationResult(
                    observation_id=(
                        observation
                        .observation_id
                    ),
                    raw_score=float(
                        raw_scores[
                            index
                        ]
                    ),
                    decision_score=float(
                        decision_scores[
                            index
                        ]
                    ),
                    anomaly_score=(
                        anomaly_scores[
                            index
                        ]
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
            observation_results
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
            IsolationForestDiagnostics(
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
                inlier_count=(
                    inlier_count
                ),
                outlier_count=(
                    outlier_count
                ),
            )
        )

        return IsolationForestResult(
            status=(
                IsolationForestStatus.OK
            ),
            config=config,
            feature_names=(
                matrix.feature_names
            ),
            observations=(
                result_tuple
            ),
            diagnostics=diagnostics,
            offset=offset,
            fitted_max_samples=int(
                model.max_samples_
            ),
        )

    # ==========================================================
    # Config / matrix compatibility
    # ==========================================================

    @staticmethod
    def _validate_config_for_matrix(
        matrix: NumericFeatureMatrix,
        config: IsolationForestConfig,
    ) -> None:

        max_features = (
            config.max_features
        )

        if (
            isinstance(
                max_features,
                int,
            )
            and
            max_features
            >
            matrix.feature_count
        ):

            raise ValueError(
                "Integer max_features cannot "
                "exceed matrix feature count."
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

        constant_names: list[
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

                constant_names.append(
                    name
                )

        return tuple(
            constant_names
        )

    # ==========================================================
    # Unfitted result
    # ==========================================================

    @staticmethod
    def _unfitted_result(
        matrix: NumericFeatureMatrix,
        config: IsolationForestConfig,
        *,
        status: IsolationForestStatus,
        constant_feature_names: tuple[
            str,
            ...,
        ],
    ) -> IsolationForestResult:

        diagnostics = (
            IsolationForestDiagnostics(
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
                inlier_count=0,
                outlier_count=0,
            )
        )

        return IsolationForestResult(
            status=status,
            config=config,
            feature_names=(
                matrix.feature_names
            ),
            observations=(),
            diagnostics=diagnostics,
            offset=None,
            fitted_max_samples=None,
        )