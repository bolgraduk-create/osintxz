"""
Shared contracts for numerical anomaly analysis.

These contracts provide a small, explicit boundary between
investigation/domain data and generic numerical algorithms.

Pipeline:

domain/application features
    ↓
AnomalyObservation
    ↓
NumericFeatureMatrix
    ↓
anomaly / clustering algorithms

The contracts intentionally contain no interpretation such as:

- suspicious
- malicious
- evidence
- identity
- relationship
- causation

They only describe numerical observations.
"""

from __future__ import annotations

from dataclasses import dataclass

from math import isfinite

from numbers import Real


# ==========================================================
# Observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class AnomalyObservation:
    """
    One numerical observation.

    observation_id:

        Stable identifier supplied by the caller.

        Examples:

            entity UUID as string
            timeline-window identifier
            account identifier
            relationship identifier

    values:

        Numerical feature vector.

        Feature meaning is defined externally by
        NumericFeatureMatrix.feature_names.
    """

    observation_id: str

    values: tuple[
        float,
        ...,
    ]

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
            self.values,
            tuple,
        ):

            raise TypeError(
                "values must be a tuple."
            )

        if not self.values:

            raise ValueError(
                "Observation must contain "
                "at least one feature."
            )

        normalized_values: list[
            float
        ] = []

        for value in self.values:

            if isinstance(
                value,
                bool,
            ):

                raise TypeError(
                    "Boolean values are not valid "
                    "numeric anomaly features."
                )

            if not isinstance(
                value,
                Real,
            ):

                raise TypeError(
                    "All anomaly features must "
                    "be real numbers."
                )

            normalized = float(
                value
            )

            if not isfinite(
                normalized
            ):

                raise ValueError(
                    "Anomaly features must be finite."
                )

            normalized_values.append(
                normalized
            )

        object.__setattr__(
            self,
            "values",
            tuple(
                normalized_values
            ),
        )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def feature_count(
        self,
    ) -> int:

        return len(
            self.values
        )


# ==========================================================
# Feature matrix
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class NumericFeatureMatrix:
    """
    Validated collection of numerical observations.

    Every observation must:

    - have a unique observation_id
    - have exactly the same feature count
    - contain only finite numerical values
    """

    feature_names: tuple[
        str,
        ...,
    ]

    observations: tuple[
        AnomalyObservation,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.feature_names,
            tuple,
        ):

            raise TypeError(
                "feature_names must be a tuple."
            )

        if not self.feature_names:

            raise ValueError(
                "At least one feature name "
                "is required."
            )

        normalized_names: list[
            str
        ] = []

        seen_names: set[
            str
        ] = set()

        for name in self.feature_names:

            if (
                not isinstance(
                    name,
                    str,
                )
                or not name.strip()
            ):

                raise ValueError(
                    "Feature names cannot be empty."
                )

            normalized = (
                name.strip()
            )

            if normalized in seen_names:

                raise ValueError(
                    f"Duplicate feature name: "
                    f"{normalized}"
                )

            seen_names.add(
                normalized
            )

            normalized_names.append(
                normalized
            )

        object.__setattr__(
            self,
            "feature_names",
            tuple(
                normalized_names
            ),
        )

        if not isinstance(
            self.observations,
            tuple,
        ):

            raise TypeError(
                "observations must be a tuple."
            )

        expected_feature_count = len(
            self.feature_names
        )

        seen_ids: set[
            str
        ] = set()

        for observation in self.observations:

            if not isinstance(
                observation,
                AnomalyObservation,
            ):

                raise TypeError(
                    "observations must contain "
                    "AnomalyObservation objects."
                )

            if (
                observation.feature_count
                !=
                expected_feature_count
            ):

                raise ValueError(
                    "Observation feature count does "
                    "not match feature_names."
                )

            if (
                observation.observation_id
                in seen_ids
            ):

                raise ValueError(
                    "Duplicate observation_id: "
                    f"{observation.observation_id}"
                )

            seen_ids.add(
                observation.observation_id
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def sample_count(
        self,
    ) -> int:

        return len(
            self.observations
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return len(
            self.feature_names
        )

    @property
    def observation_ids(
        self,
    ) -> tuple[
        str,
        ...,
    ]:

        return tuple(
            observation.observation_id
            for observation
            in self.observations
        )

    # ==========================================================
    # Deterministic ordering
    # ==========================================================

    def canonicalized(
        self,
    ) -> "NumericFeatureMatrix":
        """
        Return the same matrix with observations ordered
        deterministically by observation_id.

        This is important for stochastic algorithms whose
        internal random sampling may otherwise depend on
        incoming row order.
        """

        ordered = tuple(
            sorted(
                self.observations,
                key=lambda observation: (
                    observation.observation_id
                ),
            )
        )

        if ordered == self.observations:

            return self

        return NumericFeatureMatrix(
            feature_names=(
                self.feature_names
            ),
            observations=ordered,
        )