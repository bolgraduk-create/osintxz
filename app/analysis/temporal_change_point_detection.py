"""
Temporal change-point detection.

Detects sustained changes in temporal activity regimes.

Input:

    TemporalCorrelationResult

The correlation result provides canonical epoch-aligned
fixed-duration activity windows created in Phase 4.2.

Pipeline:

TemporalCorrelationResult
    ↓
activity series
    ↓
candidate boundary
    ↓
N windows before | N windows after
    ↓
Poisson likelihood-ratio test
    ↓
effect-size filters
    ↓
multiple-testing correction
    ↓
candidate consolidation
    ↓
TemporalChangePointDetectionResult

Change-point semantics:

A detected change point represents a statistically
supported change in activity level.

It does NOT represent:

- causation
- coordination proof
- relationship evidence
- identity evidence
- generic anomaly classification

Does NOT:

- query the database
- write to the database
- use created_at
- create TimelineEvent
- create Relationship
- create Evidence
- modify Entity Resolution
- perform burst detection
"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime

from enum import Enum

from math import (
    erfc,
    isfinite,
    log,
    log10,
    sqrt,
)

from uuid import UUID

from app.analysis.temporal_correlation import (
    TemporalCorrelationResult,
)


# ==========================================================
# Scope
# ==========================================================


class TemporalChangePointScope(
    str,
    Enum,
):
    """
    Activity dimension containing the regime change.
    """

    GLOBAL = "global"

    ENTITY = "entity"

    EVENT_TYPE = "event_type"


# ==========================================================
# Direction
# ==========================================================


class TemporalChangeDirection(
    str,
    Enum,
):
    """
    Direction of activity change.
    """

    INCREASE = "increase"

    DECREASE = "decrease"


# ==========================================================
# Multiple testing
# ==========================================================


class TemporalChangePointCorrection(
    str,
    Enum,
):
    """
    Correction across candidate boundaries of one
    activity series.
    """

    NONE = "none"

    BONFERRONI_PER_SERIES = (
        "bonferroni_per_series"
    )


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalChangePointDetectionConfig:
    """
    Change-point configuration.

    comparison_windows:

        Number of consecutive windows used on EACH
        side of one candidate boundary.

        Example for comparison_windows=3:

            [L1 L2 L3] | [R1 R2 R3]
                        ↑
                    boundary

    minimum_mean_difference:

        Minimum absolute difference between left and
        right mean activity.

    minimum_rate_ratio:

        Minimum ratio between the larger and smaller
        mean.

        If the smaller mean is zero and the larger mean
        is positive, this filter automatically passes.

    alpha:

        Significance threshold before correction.

    correction:

        Multiple-testing correction applied across all
        mathematically evaluable boundaries of one
        series.

    detect_global:
        Detect total activity regime changes.

    detect_entities:
        Detect per-Entity regime changes.

    detect_event_types:
        Detect per-event-type regime changes.
    """

    comparison_windows: int = 3

    minimum_mean_difference: float = 2.0

    minimum_rate_ratio: float = 2.0

    alpha: float = 0.01

    correction: TemporalChangePointCorrection = (
        TemporalChangePointCorrection
        .BONFERRONI_PER_SERIES
    )

    detect_global: bool = True

    detect_entities: bool = True

    detect_event_types: bool = True

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.comparison_windows,
                int,
            )
            or self.comparison_windows < 2
        ):

            raise ValueError(
                "comparison_windows must be "
                "an integer >= 2."
            )

        minimum_difference = float(
            self.minimum_mean_difference
        )

        if (
            not isfinite(
                minimum_difference
            )
            or minimum_difference < 0.0
        ):

            raise ValueError(
                "minimum_mean_difference must "
                "be finite and non-negative."
            )

        object.__setattr__(
            self,
            "minimum_mean_difference",
            minimum_difference,
        )

        minimum_ratio = float(
            self.minimum_rate_ratio
        )

        if (
            not isfinite(
                minimum_ratio
            )
            or minimum_ratio < 1.0
        ):

            raise ValueError(
                "minimum_rate_ratio must be "
                "finite and >= 1.0."
            )

        object.__setattr__(
            self,
            "minimum_rate_ratio",
            minimum_ratio,
        )

        alpha = float(
            self.alpha
        )

        if (
            not isfinite(
                alpha
            )
            or not (
                0.0
                <
                alpha
                <=
                1.0
            )
        ):

            raise ValueError(
                "alpha must be in (0, 1]."
            )

        object.__setattr__(
            self,
            "alpha",
            alpha,
        )

        if not isinstance(
            self.correction,
            TemporalChangePointCorrection,
        ):

            raise TypeError(
                "correction must be "
                "TemporalChangePointCorrection."
            )

        for field_name in (
            "detect_global",
            "detect_entities",
            "detect_event_types",
        ):

            if not isinstance(
                getattr(
                    self,
                    field_name,
                ),
                bool,
            ):

                raise TypeError(
                    f"{field_name} must be bool."
                )


# ==========================================================
# Change point
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalChangePoint:
    """
    One detected temporal regime change.

    boundary_index:

        Index of the FIRST window belonging to the new
        regime.

    Example:

        index:
            0 1 2 3 4 5 6 7 8

        change at boundary 6:

            [ ... 4 5 ] | [ 6 7 ... ]
                        ↑

    rate_ratio:

        larger_mean / smaller_mean

        None when smaller_mean == 0.

    poisson_deviance:

        Likelihood-ratio deviance comparing:

            H0: same Poisson activity rate

        against:

            H1: different activity rates

        across equally sized left/right windows.

    p_value:

        Chi-square(1) asymptotic tail probability of the
        Poisson likelihood-ratio statistic.
    """

    scope: TemporalChangePointScope

    series_id: str

    boundary_index: int

    change_time_utc: datetime

    direction: TemporalChangeDirection

    left_window_count: int

    right_window_count: int

    left_mean: float

    right_mean: float

    absolute_mean_difference: float

    rate_ratio: (
        float
        | None
    )

    poisson_deviance: float

    p_value: float

    adjusted_alpha: float

    surprise_score: float

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.scope,
            TemporalChangePointScope,
        ):

            raise TypeError(
                "scope must be "
                "TemporalChangePointScope."
            )

        normalized_id = (
            self._normalize_series_id(
                self.scope,
                self.series_id,
            )
        )

        object.__setattr__(
            self,
            "series_id",
            normalized_id,
        )

        if (
            not isinstance(
                self.boundary_index,
                int,
            )
            or self.boundary_index < 1
        ):

            raise ValueError(
                "boundary_index must be >= 1."
            )

        if not isinstance(
            self.change_time_utc,
            datetime,
        ):

            raise TypeError(
                "change_time_utc must be datetime."
            )

        if (
            self.change_time_utc.tzinfo
            is None
            or
            self.change_time_utc.utcoffset()
            is None
        ):

            raise ValueError(
                "change_time_utc must be "
                "timezone-aware."
            )

        if not isinstance(
            self.direction,
            TemporalChangeDirection,
        ):

            raise TypeError(
                "direction must be "
                "TemporalChangeDirection."
            )

        for field_name in (
            "left_window_count",
            "right_window_count",
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
                    f"{field_name} must be positive."
                )

        if (
            self.left_window_count
            !=
            self.right_window_count
        ):

            raise ValueError(
                "Change-point comparison requires "
                "equal left/right exposure."
            )

        for field_name in (
            "left_mean",
            "right_mean",
            "absolute_mean_difference",
            "poisson_deviance",
            "p_value",
            "adjusted_alpha",
            "surprise_score",
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

        if (
            self.left_mean < 0.0
            or
            self.right_mean < 0.0
        ):

            raise ValueError(
                "Activity means cannot be negative."
            )

        if self.absolute_mean_difference < 0.0:

            raise ValueError(
                "absolute_mean_difference "
                "cannot be negative."
            )

        if self.poisson_deviance < 0.0:

            raise ValueError(
                "poisson_deviance cannot "
                "be negative."
            )

        if not (
            0.0
            <=
            self.p_value
            <=
            1.0
        ):

            raise ValueError(
                "p_value must be between 0 and 1."
            )

        if not (
            0.0
            <
            self.adjusted_alpha
            <=
            1.0
        ):

            raise ValueError(
                "adjusted_alpha must be "
                "in (0, 1]."
            )

        if (
            self.p_value
            >
            self.adjusted_alpha
        ):

            raise ValueError(
                "Stored change point must satisfy "
                "its significance threshold."
            )

        if self.surprise_score < 0.0:

            raise ValueError(
                "surprise_score cannot be negative."
            )

        if self.rate_ratio is not None:

            ratio = float(
                self.rate_ratio
            )

            if (
                not isfinite(
                    ratio
                )
                or ratio < 1.0
            ):

                raise ValueError(
                    "rate_ratio must be "
                    "finite and >= 1."
                )

            object.__setattr__(
                self,
                "rate_ratio",
                ratio,
            )

        if (
            self.direction
            ==
            TemporalChangeDirection.INCREASE
            and
            not (
                self.right_mean
                >
                self.left_mean
            )
        ):

            raise ValueError(
                "INCREASE requires "
                "right_mean > left_mean."
            )

        if (
            self.direction
            ==
            TemporalChangeDirection.DECREASE
            and
            not (
                self.right_mean
                <
                self.left_mean
            )
        ):

            raise ValueError(
                "DECREASE requires "
                "right_mean < left_mean."
            )

    # ==========================================================
    # ID normalization
    # ==========================================================

    @staticmethod
    def _normalize_series_id(
        scope: TemporalChangePointScope,
        value: str,
    ) -> str:

        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):

            raise ValueError(
                "series_id cannot be empty."
            )

        normalized = (
            value.strip()
        )

        if (
            scope
            ==
            TemporalChangePointScope.GLOBAL
        ):

            if normalized.lower() != "global":

                raise ValueError(
                    "GLOBAL series_id "
                    "must be 'global'."
                )

            return "global"

        if (
            scope
            ==
            TemporalChangePointScope.ENTITY
        ):

            return str(
                UUID(
                    normalized
                )
            )

        return normalized.lower()


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalChangePointDetectionResult:
    """
    Complete Phase 4.4 change-point result.
    """

    case_id: (
        UUID
        | None
    )

    window_seconds: int

    window_starts_utc: tuple[
        datetime,
        ...,
    ]

    config: (
        TemporalChangePointDetectionConfig
    )

    change_points: tuple[
        TemporalChangePoint,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if (
            self.case_id
            is not None
            and
            not isinstance(
                self.case_id,
                UUID,
            )
        ):

            raise TypeError(
                "case_id must be UUID or None."
            )

        if (
            not isinstance(
                self.window_seconds,
                int,
            )
            or self.window_seconds <= 0
        ):

            raise ValueError(
                "window_seconds must be positive."
            )

        if not isinstance(
            self.window_starts_utc,
            tuple,
        ):

            raise TypeError(
                "window_starts_utc must be tuple."
            )

        for timestamp in (
            self.window_starts_utc
        ):

            if not isinstance(
                timestamp,
                datetime,
            ):

                raise TypeError(
                    "window starts must contain "
                    "datetime objects."
                )

            if (
                timestamp.tzinfo
                is None
                or
                timestamp.utcoffset()
                is None
            ):

                raise ValueError(
                    "window timestamps must be "
                    "timezone-aware."
                )

        if not isinstance(
            self.config,
            TemporalChangePointDetectionConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalChangePointDetectionConfig."
            )

        if not isinstance(
            self.change_points,
            tuple,
        ):

            raise TypeError(
                "change_points must be tuple."
            )

        seen: set[
            tuple[
                TemporalChangePointScope,
                str,
                int,
            ]
        ] = set()

        for change in self.change_points:

            if not isinstance(
                change,
                TemporalChangePoint,
            ):

                raise TypeError(
                    "change_points must contain "
                    "TemporalChangePoint."
                )

            if (
                change.boundary_index
                >=
                len(
                    self.window_starts_utc
                )
            ):

                raise ValueError(
                    "Change-point boundary outside "
                    "window range."
                )

            if (
                change.change_time_utc
                !=
                self.window_starts_utc[
                    change.boundary_index
                ]
            ):

                raise ValueError(
                    "Change-point timestamp does "
                    "not match boundary index."
                )

            key = (
                change.scope,
                change.series_id,
                change.boundary_index,
            )

            if key in seen:

                raise ValueError(
                    "Duplicate temporal change point."
                )

            seen.add(
                key
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def window_count(
        self,
    ) -> int:

        return len(
            self.window_starts_utc
        )

    @property
    def change_point_count(
        self,
    ) -> int:

        return len(
            self.change_points
        )

    # ==========================================================
    # Scope access
    # ==========================================================

    @property
    def global_change_points(
        self,
    ) -> tuple[
        TemporalChangePoint,
        ...,
    ]:

        return tuple(
            item
            for item
            in self.change_points
            if (
                item.scope
                ==
                TemporalChangePointScope.GLOBAL
            )
        )

    def changes_for_entity(
        self,
        entity_id: UUID,
    ) -> tuple[
        TemporalChangePoint,
        ...,
    ]:

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        target = str(
            entity_id
        )

        return tuple(
            item
            for item
            in self.change_points
            if (
                item.scope
                ==
                TemporalChangePointScope.ENTITY
                and
                item.series_id
                ==
                target
            )
        )

    def changes_for_event_type(
        self,
        event_type: str,
    ) -> tuple[
        TemporalChangePoint,
        ...,
    ]:

        target = (
            str(
                event_type
            )
            .strip()
            .lower()
        )

        return tuple(
            item
            for item
            in self.change_points
            if (
                item.scope
                ==
                TemporalChangePointScope.EVENT_TYPE
                and
                item.series_id
                ==
                target
            )
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top_change_points(
        self,
        limit: int = 10,
    ) -> tuple[
        TemporalChangePoint,
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
                "limit must be non-negative."
            )

        ordered = sorted(
            self.change_points,
            key=lambda item: (
                -item.surprise_score,
                -item.absolute_mean_difference,
                self._scope_rank(
                    item.scope
                ),
                item.series_id,
                item.boundary_index,
            ),
        )

        return tuple(
            ordered[
                :limit
            ]
        )

    @staticmethod
    def _scope_rank(
        scope: TemporalChangePointScope,
    ) -> int:

        return {
            TemporalChangePointScope.GLOBAL:
                0,

            TemporalChangePointScope.ENTITY:
                1,

            TemporalChangePointScope.EVENT_TYPE:
                2,
        }[
            scope
        ]


# ==========================================================
# Service
# ==========================================================


class TemporalChangePointDetectionService:
    """
    Pure temporal regime-change detector.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        correlation: TemporalCorrelationResult,
        config: (
            TemporalChangePointDetectionConfig
            | None
        ) = None,
    ) -> TemporalChangePointDetectionResult:
        """
        Detect sustained activity-level changes.

        No database writes are performed.
        """

        if not isinstance(
            correlation,
            TemporalCorrelationResult,
        ):

            raise TypeError(
                "correlation must be "
                "TemporalCorrelationResult."
            )

        config = (
            config
            or
            TemporalChangePointDetectionConfig()
        )

        if not isinstance(
            config,
            TemporalChangePointDetectionConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalChangePointDetectionConfig."
            )

        if correlation.window_count == 0:

            return (
                TemporalChangePointDetectionResult(
                    case_id=(
                        correlation.case_id
                    ),
                    window_seconds=(
                        correlation.window_seconds
                    ),
                    window_starts_utc=(),
                    config=config,
                    change_points=(),
                )
            )

        series = (
            self._build_series(
                correlation,
                config=config,
            )
        )

        changes: list[
            TemporalChangePoint
        ] = []

        for (
            scope,
            series_id,
            counts,
        ) in series:

            candidates = (
                self._detect_series(
                    scope=scope,
                    series_id=series_id,
                    counts=counts,
                    window_starts=(
                        correlation
                        .window_starts_utc
                    ),
                    config=config,
                )
            )

            changes.extend(
                self._consolidate_candidates(
                    candidates
                )
            )

        changes.sort(
            key=lambda item: (
                self._scope_rank(
                    item.scope
                ),
                item.series_id,
                item.boundary_index,
            )
        )

        return (
            TemporalChangePointDetectionResult(
                case_id=(
                    correlation.case_id
                ),
                window_seconds=(
                    correlation.window_seconds
                ),
                window_starts_utc=(
                    correlation
                    .window_starts_utc
                ),
                config=config,
                change_points=tuple(
                    changes
                ),
            )
        )

    # ==========================================================
    # Series construction
    # ==========================================================

    def _build_series(
        self,
        correlation: TemporalCorrelationResult,
        *,
        config: TemporalChangePointDetectionConfig,
    ) -> tuple[
        tuple[
            TemporalChangePointScope,
            str,
            tuple[
                int,
                ...,
            ],
        ],
        ...,
    ]:

        result: list[
            tuple[
                TemporalChangePointScope,
                str,
                tuple[
                    int,
                    ...,
                ],
            ]
        ] = []

        window_count = (
            correlation.window_count
        )

        # ======================================================
        # Global activity
        # ======================================================

        if config.detect_global:

            global_counts = [
                0
                for _
                in range(
                    window_count
                )
            ]

            # Event-type series partition all accepted
            # observations exactly once.
            for series in (
                correlation
                .event_type_series
            ):

                for (
                    index,
                    count,
                ) in enumerate(
                    series.counts
                ):

                    global_counts[
                        index
                    ] += count

            result.append(
                (
                    TemporalChangePointScope.GLOBAL,
                    "global",
                    tuple(
                        global_counts
                    ),
                )
            )

        # ======================================================
        # Entity activity
        # ======================================================

        if config.detect_entities:

            for series in (
                correlation.entity_series
            ):

                result.append(
                    (
                        TemporalChangePointScope.ENTITY,
                        series.series_id,
                        series.counts,
                    )
                )

        # ======================================================
        # Event-type activity
        # ======================================================

        if config.detect_event_types:

            for series in (
                correlation
                .event_type_series
            ):

                result.append(
                    (
                        TemporalChangePointScope
                        .EVENT_TYPE,
                        series.series_id,
                        series.counts,
                    )
                )

        result.sort(
            key=lambda item: (
                self._scope_rank(
                    item[
                        0
                    ]
                ),
                item[
                    1
                ],
            )
        )

        return tuple(
            result
        )

    # ==========================================================
    # One series
    # ==========================================================

    def _detect_series(
        self,
        *,
        scope: TemporalChangePointScope,
        series_id: str,
        counts: tuple[
            int,
            ...,
        ],
        window_starts: tuple[
            datetime,
            ...,
        ],
        config: TemporalChangePointDetectionConfig,
    ) -> tuple[
        TemporalChangePoint,
        ...,
    ]:

        if len(
            counts
        ) != len(
            window_starts
        ):

            raise ValueError(
                "Change-point series/window "
                "length mismatch."
            )

        comparison_windows = (
            config.comparison_windows
        )

        evaluable_boundaries = (
            len(
                counts
            )
            -
            (
                2
                *
                comparison_windows
            )
            +
            1
        )

        if evaluable_boundaries <= 0:

            return ()

        adjusted_alpha = (
            self._adjusted_alpha(
                config,
                evaluable_boundaries=(
                    evaluable_boundaries
                ),
            )
        )

        candidates: list[
            TemporalChangePoint
        ] = []

        for boundary_index in range(
            comparison_windows,
            (
                len(
                    counts
                )
                -
                comparison_windows
                +
                1
            ),
        ):

            left = counts[
                (
                    boundary_index
                    -
                    comparison_windows
                ):
                boundary_index
            ]

            right = counts[
                boundary_index:
                (
                    boundary_index
                    +
                    comparison_windows
                )
            ]

            left_mean = (
                sum(
                    left
                )
                /
                comparison_windows
            )

            right_mean = (
                sum(
                    right
                )
                /
                comparison_windows
            )

            difference = abs(
                right_mean
                -
                left_mean
            )

            if (
                difference
                <
                config.minimum_mean_difference
            ):

                continue

            smaller_mean = min(
                left_mean,
                right_mean,
            )

            larger_mean = max(
                left_mean,
                right_mean,
            )

            if smaller_mean > 0.0:

                rate_ratio = (
                    larger_mean
                    /
                    smaller_mean
                )

                if (
                    rate_ratio
                    <
                    config.minimum_rate_ratio
                ):

                    continue

            else:

                rate_ratio = None

                if larger_mean <= 0.0:

                    continue

            left_total = sum(
                left
            )

            right_total = sum(
                right
            )

            (
                deviance,
                p_value,
            ) = (
                self._poisson_rate_change_test(
                    left_total=left_total,
                    right_total=right_total,
                )
            )

            if (
                p_value
                >
                adjusted_alpha
            ):

                continue

            if (
                right_mean
                >
                left_mean
            ):

                direction = (
                    TemporalChangeDirection
                    .INCREASE
                )

            else:

                direction = (
                    TemporalChangeDirection
                    .DECREASE
                )

            candidates.append(
                TemporalChangePoint(
                    scope=scope,
                    series_id=series_id,
                    boundary_index=(
                        boundary_index
                    ),
                    change_time_utc=(
                        window_starts[
                            boundary_index
                        ]
                    ),
                    direction=direction,
                    left_window_count=(
                        comparison_windows
                    ),
                    right_window_count=(
                        comparison_windows
                    ),
                    left_mean=(
                        left_mean
                    ),
                    right_mean=(
                        right_mean
                    ),
                    absolute_mean_difference=(
                        difference
                    ),
                    rate_ratio=(
                        rate_ratio
                    ),
                    poisson_deviance=(
                        deviance
                    ),
                    p_value=(
                        p_value
                    ),
                    adjusted_alpha=(
                        adjusted_alpha
                    ),
                    surprise_score=(
                        self._surprise_score(
                            p_value
                        )
                    ),
                )
            )

        return tuple(
            candidates
        )

    # ==========================================================
    # Candidate consolidation
    # ==========================================================

    @staticmethod
    def _consolidate_candidates(
        candidates: tuple[
            TemporalChangePoint,
            ...,
        ],
    ) -> tuple[
        TemporalChangePoint,
        ...,
    ]:
        """
        Adjacent candidate boundaries around one broad
        transition frequently become significant.

        They represent one regime transition, not several.

        Consecutive significant boundaries are grouped,
        then the strongest boundary is retained.

        Selection order:

        1. smallest p-value
        2. largest mean difference
        3. smallest boundary index
        """

        if not candidates:

            return ()

        ordered = sorted(
            candidates,
            key=lambda item: (
                item.boundary_index
            ),
        )

        groups: list[
            list[
                TemporalChangePoint
            ]
        ] = []

        current: list[
            TemporalChangePoint
        ] = []

        for candidate in ordered:

            if not current:

                current.append(
                    candidate
                )

                continue

            previous = current[
                -1
            ]

            if (
                candidate.boundary_index
                ==
                previous.boundary_index
                +
                1
            ):

                current.append(
                    candidate
                )

            else:

                groups.append(
                    current
                )

                current = [
                    candidate
                ]

        if current:

            groups.append(
                current
            )

        selected = [
            min(
                group,
                key=lambda item: (
                    item.p_value,
                    -item.absolute_mean_difference,
                    item.boundary_index,
                ),
            )
            for group
            in groups
        ]

        selected.sort(
            key=lambda item: (
                item.boundary_index
            )
        )

        return tuple(
            selected
        )

    # ==========================================================
    # Poisson rate-change test
    # ==========================================================

    @staticmethod
    def _poisson_rate_change_test(
        *,
        left_total: int,
        right_total: int,
    ) -> tuple[
        float,
        float,
    ]:
        """
        Likelihood-ratio test for equal Poisson rates.

        Left and right exposures are equal because the
        same number of fixed-duration windows is used on
        each side.

        Null hypothesis:

            lambda_left == lambda_right

        Under H0 the expected total on each side is:

            (left_total + right_total) / 2

        Deviance:

            D = 2 * sum(
                observed * log(observed / expected)
            )

        with the standard convention:

            0 * log(0 / expected) = 0

        Asymptotically:

            D ~ ChiSquare(df=1)

        For one degree of freedom:

            P(ChiSquare >= D)
            =
            erfc(sqrt(D / 2))
        """

        if (
            not isinstance(
                left_total,
                int,
            )
            or left_total < 0
        ):

            raise ValueError(
                "left_total must be a "
                "non-negative integer."
            )

        if (
            not isinstance(
                right_total,
                int,
            )
            or right_total < 0
        ):

            raise ValueError(
                "right_total must be a "
                "non-negative integer."
            )

        total = (
            left_total
            +
            right_total
        )

        if total == 0:

            return (
                0.0,
                1.0,
            )

        expected = (
            total
            /
            2.0
        )

        deviance = 0.0

        for observed in (
            left_total,
            right_total,
        ):

            if observed == 0:

                continue

            deviance += (
                2.0
                *
                observed
                *
                log(
                    observed
                    /
                    expected
                )
            )

        # Floating-point guard.
        deviance = max(
            0.0,
            deviance,
        )

        p_value = erfc(
            sqrt(
                deviance
                /
                2.0
            )
        )

        p_value = max(
            0.0,
            min(
                1.0,
                p_value,
            ),
        )

        return (
            deviance,
            p_value,
        )

    # ==========================================================
    # Multiple testing
    # ==========================================================

    @staticmethod
    def _adjusted_alpha(
        config: TemporalChangePointDetectionConfig,
        *,
        evaluable_boundaries: int,
    ) -> float:

        if (
            config.correction
            ==
            TemporalChangePointCorrection.NONE
        ):

            return config.alpha

        divisor = max(
            1,
            evaluable_boundaries,
        )

        return (
            config.alpha
            /
            divisor
        )

    # ==========================================================
    # Surprise
    # ==========================================================

    @staticmethod
    def _surprise_score(
        p_value: float,
    ) -> float:

        if p_value <= 0.0:

            return 300.0

        return min(
            300.0,
            (
                -log10(
                    p_value
                )
            ),
        )

    # ==========================================================
    # Scope order
    # ==========================================================

    @staticmethod
    def _scope_rank(
        scope: TemporalChangePointScope,
    ) -> int:

        return {
            TemporalChangePointScope.GLOBAL:
                0,

            TemporalChangePointScope.ENTITY:
                1,

            TemporalChangePointScope.EVENT_TYPE:
                2,
        }[
            scope
        ]