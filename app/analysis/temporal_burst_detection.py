"""
Temporal burst detection.

Detects statistically unusual short-term increases in
temporal activity.

Input:

    TemporalCorrelationResult

The correlation result already contains the canonical,
epoch-aligned activity windows produced in Phase 4.2.

Pipeline:

TemporalCorrelationResult
    ↓
activity series
    ↓
historical rolling baseline
    ↓
Poisson upper-tail probability
    ↓
burst windows
    ↓
consecutive burst episodes

Detection is deliberately historical:

    current window
        is compared only with PREVIOUS windows.

This prevents the candidate burst itself from directly
contaminating its own baseline.

Important semantic boundaries:

Burst
    != anomaly proof
    != causation
    != coordination proof
    != evidence
    != identity evidence

Does NOT:

- query the database
- write to the database
- use created_at
- create TimelineEvent
- modify TimelineEvent
- perform change-point detection
- perform generic anomaly detection
- create Evidence
- create Relationships
"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime

from enum import Enum

from math import (
    exp,
    isfinite,
    lgamma,
    log,
    log10,
    sqrt,
)

from uuid import UUID

from app.analysis.temporal_correlation import (
    TemporalCorrelationResult,
)


# ==========================================================
# Burst scope
# ==========================================================


class TemporalBurstScope(
    str,
    Enum,
):
    """
    Activity dimension in which a burst was detected.
    """

    GLOBAL = "global"

    ENTITY = "entity"

    EVENT_TYPE = "event_type"


# ==========================================================
# Multiple-testing correction
# ==========================================================


class TemporalBurstCorrection(
    str,
    Enum,
):
    """
    Correction applied across tested windows of each
    individual activity series.

    NONE:
        alpha is used directly.

    BONFERRONI_PER_SERIES:
        alpha / number_of_evaluable_windows

    This correction controls repeated temporal testing
    inside one series.

    It intentionally does not imply statistical
    independence between different Entity series.
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
class TemporalBurstDetectionConfig:
    """
    Burst-detection configuration.

    baseline_windows:

        Maximum number of previous windows used for the
        historical baseline.

    minimum_baseline_windows:

        Minimum number of historical windows required
        before a current window may be evaluated.

    minimum_events:

        Absolute minimum activity count required for a
        burst.

    minimum_excess:

        Observed count must exceed the historical mean
        by at least this amount.

    minimum_ratio:

        For a non-zero baseline:

            observed / baseline_mean

        must be at least this value.

        A zero historical baseline is handled separately:
        positive activity may still be evaluated using
        the Poisson model.

    alpha:

        Maximum Poisson upper-tail probability before
        multiple-testing correction.

    correction:

        Temporal multiple-testing correction.

    detect_global:

        Detect bursts over total event activity.

    detect_entities:

        Detect per-Entity bursts.

    detect_event_types:

        Detect per-event-type bursts.
    """

    baseline_windows: int = 6

    minimum_baseline_windows: int = 3

    minimum_events: int = 3

    minimum_excess: float = 2.0

    minimum_ratio: float = 2.0

    alpha: float = 0.01

    correction: TemporalBurstCorrection = (
        TemporalBurstCorrection
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
                self.baseline_windows,
                int,
            )
            or
            self.baseline_windows < 1
        ):

            raise ValueError(
                "baseline_windows must be "
                "a positive integer."
            )

        if (
            not isinstance(
                self.minimum_baseline_windows,
                int,
            )
            or
            self.minimum_baseline_windows < 1
        ):

            raise ValueError(
                "minimum_baseline_windows must "
                "be a positive integer."
            )

        if (
            self.minimum_baseline_windows
            >
            self.baseline_windows
        ):

            raise ValueError(
                "minimum_baseline_windows cannot "
                "exceed baseline_windows."
            )

        if (
            not isinstance(
                self.minimum_events,
                int,
            )
            or
            self.minimum_events < 1
        ):

            raise ValueError(
                "minimum_events must be "
                "a positive integer."
            )

        minimum_excess = float(
            self.minimum_excess
        )

        if (
            not isfinite(
                minimum_excess
            )
            or minimum_excess < 0.0
        ):

            raise ValueError(
                "minimum_excess must be finite "
                "and non-negative."
            )

        object.__setattr__(
            self,
            "minimum_excess",
            minimum_excess,
        )

        minimum_ratio = float(
            self.minimum_ratio
        )

        if (
            not isfinite(
                minimum_ratio
            )
            or minimum_ratio < 1.0
        ):

            raise ValueError(
                "minimum_ratio must be finite "
                "and >= 1.0."
            )

        object.__setattr__(
            self,
            "minimum_ratio",
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
            TemporalBurstCorrection,
        ):

            raise TypeError(
                "correction must be "
                "TemporalBurstCorrection."
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
# Burst
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalBurst:
    """
    One statistically significant burst window.

    baseline_mean:
        Mean count over preceding baseline windows.

    baseline_standard_deviation:
        Population standard deviation of baseline counts.

    activity_ratio:
        observed / baseline_mean.

        None when baseline_mean == 0.

    z_score:
        Classical standardized diagnostic.

        None when baseline variance == 0.

        Burst detection itself does NOT depend on this
        score.

    poisson_p_value:
        Probability of observing at least observed_count
        events under Poisson(lambda=baseline_mean).

    surprise_score:

        -log10(p)

        capped for numerical safety.

        Kept separate from activity ratio and count.
    """

    scope: TemporalBurstScope

    series_id: str

    window_index: int

    window_start_utc: datetime

    observed_count: int

    baseline_window_count: int

    baseline_mean: float

    baseline_standard_deviation: float

    excess_count: float

    activity_ratio: (
        float
        | None
    )

    z_score: (
        float
        | None
    )

    poisson_p_value: float

    adjusted_alpha: float

    surprise_score: float

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.scope,
            TemporalBurstScope,
        ):

            raise TypeError(
                "scope must be TemporalBurstScope."
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
                self.window_index,
                int,
            )
            or self.window_index < 0
        ):

            raise ValueError(
                "window_index must be "
                "non-negative."
            )

        if not isinstance(
            self.window_start_utc,
            datetime,
        ):

            raise TypeError(
                "window_start_utc must "
                "be datetime."
            )

        if (
            self.window_start_utc.tzinfo
            is None
            or
            self.window_start_utc.utcoffset()
            is None
        ):

            raise ValueError(
                "window_start_utc must be "
                "timezone-aware."
            )

        if (
            not isinstance(
                self.observed_count,
                int,
            )
            or self.observed_count < 0
        ):

            raise ValueError(
                "observed_count must be "
                "non-negative."
            )

        if (
            not isinstance(
                self.baseline_window_count,
                int,
            )
            or
            self.baseline_window_count < 1
        ):

            raise ValueError(
                "baseline_window_count must "
                "be positive."
            )

        for field_name in (
            "baseline_mean",
            "baseline_standard_deviation",
            "excess_count",
            "poisson_p_value",
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

        if self.baseline_mean < 0.0:

            raise ValueError(
                "baseline_mean cannot be negative."
            )

        if (
            self.baseline_standard_deviation
            <
            0.0
        ):

            raise ValueError(
                "baseline_standard_deviation "
                "cannot be negative."
            )

        if self.excess_count < 0.0:

            raise ValueError(
                "Burst excess_count cannot "
                "be negative."
            )

        if not (
            0.0
            <=
            self.poisson_p_value
            <=
            1.0
        ):

            raise ValueError(
                "poisson_p_value must be "
                "between 0 and 1."
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
            self.poisson_p_value
            >
            self.adjusted_alpha
        ):

            raise ValueError(
                "Stored burst must satisfy "
                "its statistical threshold."
            )

        if self.surprise_score < 0.0:

            raise ValueError(
                "surprise_score cannot "
                "be negative."
            )

        if (
            self.activity_ratio
            is not None
        ):

            ratio = float(
                self.activity_ratio
            )

            if (
                not isfinite(
                    ratio
                )
                or ratio < 0.0
            ):

                raise ValueError(
                    "activity_ratio must be "
                    "finite and non-negative."
                )

            object.__setattr__(
                self,
                "activity_ratio",
                ratio,
            )

        if self.z_score is not None:

            z_score = float(
                self.z_score
            )

            if not isfinite(
                z_score
            ):

                raise ValueError(
                    "z_score must be finite."
                )

            object.__setattr__(
                self,
                "z_score",
                z_score,
            )

    # ==========================================================
    # Series normalization
    # ==========================================================

    @staticmethod
    def _normalize_series_id(
        scope: TemporalBurstScope,
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
            TemporalBurstScope.GLOBAL
        ):

            if normalized.lower() != "global":

                raise ValueError(
                    "GLOBAL burst series_id "
                    "must be 'global'."
                )

            return "global"

        if (
            scope
            ==
            TemporalBurstScope.ENTITY
        ):

            return str(
                UUID(
                    normalized
                )
            )

        return normalized.lower()

    # ==========================================================
    # Diagnostics
    # ==========================================================

    @property
    def zero_baseline(
        self,
    ) -> bool:

        return (
            self.baseline_mean
            ==
            0.0
        )


# ==========================================================
# Burst episode
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalBurstEpisode:
    """
    Consecutive burst windows belonging to the same
    temporal series.
    """

    scope: TemporalBurstScope

    series_id: str

    first_window_index: int

    last_window_index: int

    first_window_start_utc: datetime

    last_window_start_utc: datetime

    burst_window_count: int

    peak_window_index: int

    peak_observed_count: int

    peak_surprise_score: float

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.scope,
            TemporalBurstScope,
        ):

            raise TypeError(
                "scope must be TemporalBurstScope."
            )

        normalized = (
            TemporalBurst
            ._normalize_series_id(
                self.scope,
                self.series_id,
            )
        )

        object.__setattr__(
            self,
            "series_id",
            normalized,
        )

        for field_name in (
            "first_window_index",
            "last_window_index",
            "peak_window_index",
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
                    "non-negative."
                )

        if (
            self.last_window_index
            <
            self.first_window_index
        ):

            raise ValueError(
                "Episode window range is invalid."
            )

        if not (
            self.first_window_index
            <=
            self.peak_window_index
            <=
            self.last_window_index
        ):

            raise ValueError(
                "peak_window_index must belong "
                "to the episode."
            )

        expected_count = (
            self.last_window_index
            -
            self.first_window_index
            +
            1
        )

        if (
            self.burst_window_count
            !=
            expected_count
        ):

            raise ValueError(
                "burst_window_count must match "
                "consecutive episode length."
            )

        if (
            not isinstance(
                self.peak_observed_count,
                int,
            )
            or self.peak_observed_count < 0
        ):

            raise ValueError(
                "peak_observed_count must "
                "be non-negative."
            )

        peak_surprise = float(
            self.peak_surprise_score
        )

        if (
            not isfinite(
                peak_surprise
            )
            or peak_surprise < 0.0
        ):

            raise ValueError(
                "peak_surprise_score must "
                "be finite and non-negative."
            )

        object.__setattr__(
            self,
            "peak_surprise_score",
            peak_surprise,
        )

        for timestamp in (
            self.first_window_start_utc,
            self.last_window_start_utc,
        ):

            if not isinstance(
                timestamp,
                datetime,
            ):

                raise TypeError(
                    "Episode timestamps must "
                    "be datetime."
                )

            if (
                timestamp.tzinfo
                is None
                or
                timestamp.utcoffset()
                is None
            ):

                raise ValueError(
                    "Episode timestamps must "
                    "be timezone-aware."
                )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalBurstDetectionResult:
    """
    Complete Phase 4.3 burst-detection result.
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

    config: TemporalBurstDetectionConfig

    bursts: tuple[
        TemporalBurst,
        ...,
    ]

    episodes: tuple[
        TemporalBurstEpisode,
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
                "window_starts_utc must "
                "be tuple."
            )

        for timestamp in (
            self.window_starts_utc
        ):

            if not isinstance(
                timestamp,
                datetime,
            ):

                raise TypeError(
                    "Window starts must contain "
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
                    "Window starts must be "
                    "timezone-aware."
                )

        if not isinstance(
            self.config,
            TemporalBurstDetectionConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalBurstDetectionConfig."
            )

        if not isinstance(
            self.bursts,
            tuple,
        ):

            raise TypeError(
                "bursts must be tuple."
            )

        seen: set[
            tuple[
                TemporalBurstScope,
                str,
                int,
            ]
        ] = set()

        for burst in self.bursts:

            if not isinstance(
                burst,
                TemporalBurst,
            ):

                raise TypeError(
                    "bursts must contain "
                    "TemporalBurst."
                )

            if (
                burst.window_index
                >=
                len(
                    self.window_starts_utc
                )
            ):

                raise ValueError(
                    "Burst window index outside "
                    "analysis window range."
                )

            if (
                burst.window_start_utc
                !=
                self.window_starts_utc[
                    burst.window_index
                ]
            ):

                raise ValueError(
                    "Burst window timestamp "
                    "does not match index."
                )

            key = (
                burst.scope,
                burst.series_id,
                burst.window_index,
            )

            if key in seen:

                raise ValueError(
                    "Duplicate temporal burst."
                )

            seen.add(
                key
            )

        if not isinstance(
            self.episodes,
            tuple,
        ):

            raise TypeError(
                "episodes must be tuple."
            )

        for episode in self.episodes:

            if not isinstance(
                episode,
                TemporalBurstEpisode,
            ):

                raise TypeError(
                    "episodes must contain "
                    "TemporalBurstEpisode."
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
    def burst_count(
        self,
    ) -> int:

        return len(
            self.bursts
        )

    @property
    def episode_count(
        self,
    ) -> int:

        return len(
            self.episodes
        )

    # ==========================================================
    # Scope access
    # ==========================================================

    @property
    def global_bursts(
        self,
    ) -> tuple[
        TemporalBurst,
        ...,
    ]:

        return tuple(
            burst
            for burst
            in self.bursts
            if (
                burst.scope
                ==
                TemporalBurstScope.GLOBAL
            )
        )

    def bursts_for_entity(
        self,
        entity_id: UUID,
    ) -> tuple[
        TemporalBurst,
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
            burst
            for burst
            in self.bursts
            if (
                burst.scope
                ==
                TemporalBurstScope.ENTITY
                and
                burst.series_id
                ==
                target
            )
        )

    def bursts_for_event_type(
        self,
        event_type: str,
    ) -> tuple[
        TemporalBurst,
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
            burst
            for burst
            in self.bursts
            if (
                burst.scope
                ==
                TemporalBurstScope.EVENT_TYPE
                and
                burst.series_id
                ==
                target
            )
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top_bursts(
        self,
        limit: int = 10,
    ) -> tuple[
        TemporalBurst,
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
                "limit must be "
                "non-negative."
            )

        ordered = sorted(
            self.bursts,
            key=lambda item: (
                -item.surprise_score,
                -item.observed_count,
                self._scope_rank(
                    item.scope
                ),
                item.series_id,
                item.window_index,
            ),
        )

        return tuple(
            ordered[
                :limit
            ]
        )

    @staticmethod
    def _scope_rank(
        scope: TemporalBurstScope,
    ) -> int:

        return {
            TemporalBurstScope.GLOBAL:
                0,

            TemporalBurstScope.ENTITY:
                1,

            TemporalBurstScope.EVENT_TYPE:
                2,
        }[
            scope
        ]


# ==========================================================
# Service
# ==========================================================


class TemporalBurstDetectionService:
    """
    Pure statistical burst detector.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        correlation: TemporalCorrelationResult,
        config: (
            TemporalBurstDetectionConfig
            | None
        ) = None,
    ) -> TemporalBurstDetectionResult:
        """
        Detect short-term activity bursts.

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
            TemporalBurstDetectionConfig()
        )

        if not isinstance(
            config,
            TemporalBurstDetectionConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalBurstDetectionConfig."
            )

        window_count = (
            correlation.window_count
        )

        if window_count == 0:

            return (
                TemporalBurstDetectionResult(
                    case_id=(
                        correlation.case_id
                    ),
                    window_seconds=(
                        correlation.window_seconds
                    ),
                    window_starts_utc=(),
                    config=config,
                    bursts=(),
                    episodes=(),
                )
            )

        series = (
            self._build_series(
                correlation,
                config=config,
            )
        )

        bursts: list[
            TemporalBurst
        ] = []

        for (
            scope,
            series_id,
            counts,
        ) in series:

            bursts.extend(
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

        bursts.sort(
            key=lambda item: (
                self._scope_rank(
                    item.scope
                ),
                item.series_id,
                item.window_index,
            )
        )

        burst_tuple = tuple(
            bursts
        )

        episodes = (
            self._build_episodes(
                burst_tuple
            )
        )

        return (
            TemporalBurstDetectionResult(
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
                bursts=burst_tuple,
                episodes=episodes,
            )
        )

    # ==========================================================
    # Series construction
    # ==========================================================

    def _build_series(
        self,
        correlation: TemporalCorrelationResult,
        *,
        config: TemporalBurstDetectionConfig,
    ) -> tuple[
        tuple[
            TemporalBurstScope,
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
                TemporalBurstScope,
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
        # Global
        # ======================================================

        if config.detect_global:

            global_counts = [
                0
                for _
                in range(
                    window_count
                )
            ]

            # Event-type series cover every accepted
            # temporal observation exactly once.
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
                    TemporalBurstScope.GLOBAL,
                    "global",
                    tuple(
                        global_counts
                    ),
                )
            )

        # ======================================================
        # Entities
        # ======================================================

        if config.detect_entities:

            for series in (
                correlation.entity_series
            ):

                result.append(
                    (
                        TemporalBurstScope.ENTITY,
                        series.series_id,
                        series.counts,
                    )
                )

        # ======================================================
        # Event types
        # ======================================================

        if config.detect_event_types:

            for series in (
                correlation
                .event_type_series
            ):

                result.append(
                    (
                        TemporalBurstScope
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
        scope: TemporalBurstScope,
        series_id: str,
        counts: tuple[
            int,
            ...,
        ],
        window_starts: tuple[
            datetime,
            ...,
        ],
        config: TemporalBurstDetectionConfig,
    ) -> list[
        TemporalBurst
    ]:

        if len(
            counts
        ) != len(
            window_starts
        ):

            raise ValueError(
                "Burst series and window "
                "counts must match."
            )

        evaluable_windows = max(
            0,
            (
                len(
                    counts
                )
                -
                config.minimum_baseline_windows
            ),
        )

        adjusted_alpha = (
            self._adjusted_alpha(
                config,
                evaluable_windows=(
                    evaluable_windows
                ),
            )
        )

        bursts: list[
            TemporalBurst
        ] = []

        for window_index in range(
            config.minimum_baseline_windows,
            len(
                counts
            ),
        ):

            baseline_start = max(
                0,
                (
                    window_index
                    -
                    config.baseline_windows
                ),
            )

            baseline = counts[
                baseline_start:
                window_index
            ]

            if (
                len(
                    baseline
                )
                <
                config.minimum_baseline_windows
            ):

                continue

            observed = counts[
                window_index
            ]

            if (
                observed
                <
                config.minimum_events
            ):

                continue

            baseline_mean = (
                sum(
                    baseline
                )
                /
                len(
                    baseline
                )
            )

            excess = (
                observed
                -
                baseline_mean
            )

            if (
                excess
                <
                config.minimum_excess
            ):

                continue

            if baseline_mean > 0.0:

                ratio = (
                    observed
                    /
                    baseline_mean
                )

                if (
                    ratio
                    <
                    config.minimum_ratio
                ):

                    continue

            else:

                ratio = None

                if observed <= 0:

                    continue

            p_value = (
                self._poisson_survival(
                    observed,
                    baseline_mean,
                )
            )

            if (
                p_value
                >
                adjusted_alpha
            ):

                continue

            baseline_std = (
                self._population_std(
                    baseline,
                    mean_value=(
                        baseline_mean
                    ),
                )
            )

            if baseline_std > 0.0:

                z_score = (
                    excess
                    /
                    baseline_std
                )

            else:

                z_score = None

            surprise_score = (
                self._surprise_score(
                    p_value
                )
            )

            bursts.append(
                TemporalBurst(
                    scope=scope,
                    series_id=series_id,
                    window_index=(
                        window_index
                    ),
                    window_start_utc=(
                        window_starts[
                            window_index
                        ]
                    ),
                    observed_count=(
                        observed
                    ),
                    baseline_window_count=len(
                        baseline
                    ),
                    baseline_mean=(
                        baseline_mean
                    ),
                    baseline_standard_deviation=(
                        baseline_std
                    ),
                    excess_count=(
                        excess
                    ),
                    activity_ratio=(
                        ratio
                    ),
                    z_score=(
                        z_score
                    ),
                    poisson_p_value=(
                        p_value
                    ),
                    adjusted_alpha=(
                        adjusted_alpha
                    ),
                    surprise_score=(
                        surprise_score
                    ),
                )
            )

        return bursts

    # ==========================================================
    # Multiple testing
    # ==========================================================

    @staticmethod
    def _adjusted_alpha(
        config: TemporalBurstDetectionConfig,
        *,
        evaluable_windows: int,
    ) -> float:

        if (
            config.correction
            ==
            TemporalBurstCorrection.NONE
        ):

            return config.alpha

        divisor = max(
            1,
            evaluable_windows,
        )

        return (
            config.alpha
            /
            divisor
        )

    # ==========================================================
    # Burst episodes
    # ==========================================================

    def _build_episodes(
        self,
        bursts: tuple[
            TemporalBurst,
            ...,
        ],
    ) -> tuple[
        TemporalBurstEpisode,
        ...,
    ]:

        if not bursts:

            return ()

        groups: dict[
            tuple[
                TemporalBurstScope,
                str,
            ],
            list[
                TemporalBurst
            ],
        ] = {}

        for burst in bursts:

            key = (
                burst.scope,
                burst.series_id,
            )

            groups.setdefault(
                key,
                [],
            ).append(
                burst
            )

        episodes: list[
            TemporalBurstEpisode
        ] = []

        for (
            scope,
            series_id,
        ) in sorted(
            groups,
            key=lambda item: (
                self._scope_rank(
                    item[
                        0
                    ]
                ),
                item[
                    1
                ],
            ),
        ):

            series_bursts = sorted(
                groups[
                    (
                        scope,
                        series_id,
                    )
                ],
                key=lambda item: (
                    item.window_index
                ),
            )

            current: list[
                TemporalBurst
            ] = []

            for burst in series_bursts:

                if not current:

                    current.append(
                        burst
                    )

                    continue

                previous = current[
                    -1
                ]

                if (
                    burst.window_index
                    ==
                    previous.window_index
                    +
                    1
                ):

                    current.append(
                        burst
                    )

                else:

                    episodes.append(
                        self._make_episode(
                            current
                        )
                    )

                    current = [
                        burst
                    ]

            if current:

                episodes.append(
                    self._make_episode(
                        current
                    )
                )

        return tuple(
            episodes
        )

    @staticmethod
    def _make_episode(
        bursts: list[
            TemporalBurst
        ],
    ) -> TemporalBurstEpisode:

        if not bursts:

            raise ValueError(
                "Cannot build empty burst episode."
            )

        ordered = sorted(
            bursts,
            key=lambda item: (
                item.window_index
            ),
        )

        first = ordered[
            0
        ]

        last = ordered[
            -1
        ]

        peak = max(
            ordered,
            key=lambda item: (
                item.surprise_score,
                item.observed_count,
                -item.window_index,
            ),
        )

        return TemporalBurstEpisode(
            scope=first.scope,
            series_id=(
                first.series_id
            ),
            first_window_index=(
                first.window_index
            ),
            last_window_index=(
                last.window_index
            ),
            first_window_start_utc=(
                first.window_start_utc
            ),
            last_window_start_utc=(
                last.window_start_utc
            ),
            burst_window_count=len(
                ordered
            ),
            peak_window_index=(
                peak.window_index
            ),
            peak_observed_count=(
                peak.observed_count
            ),
            peak_surprise_score=(
                peak.surprise_score
            ),
        )

    # ==========================================================
    # Baseline standard deviation
    # ==========================================================

    @staticmethod
    def _population_std(
        values: tuple[
            int,
            ...,
        ],
        *,
        mean_value: float,
    ) -> float:

        if not values:

            return 0.0

        variance = (
            sum(
                (
                    value
                    -
                    mean_value
                )
                ** 2
                for value
                in values
            )
            /
            len(
                values
            )
        )

        return sqrt(
            variance
        )

    # ==========================================================
    # Poisson survival probability
    # ==========================================================

    @staticmethod
    def _poisson_survival(
        observed: int,
        expected: float,
    ) -> float:
        """
        Calculate:

            P(X >= observed)

        for:

            X ~ Poisson(expected)

        Uses the probability at `observed` followed by a
        recurrence over the upper tail.

        Burst candidates already require elevated
        observed activity, so summing from the observed
        value upward is numerically appropriate here.
        """

        if (
            not isinstance(
                observed,
                int,
            )
            or observed < 0
        ):

            raise ValueError(
                "observed must be "
                "a non-negative integer."
            )

        expected = float(
            expected
        )

        if (
            not isfinite(
                expected
            )
            or expected < 0.0
        ):

            raise ValueError(
                "expected must be finite "
                "and non-negative."
            )

        if observed <= 0:

            return 1.0

        if expected == 0.0:

            return 0.0

        log_probability = (
            -expected
            +
            (
                observed
                *
                log(
                    expected
                )
            )
            -
            lgamma(
                observed
                +
                1
            )
        )

        term = exp(
            log_probability
        )

        tail = term

        current = observed

        # The tail rapidly converges for burst candidates.
        for _ in range(
            100000
        ):

            current += 1

            term *= (
                expected
                /
                current
            )

            tail += term

            if term == 0.0:

                break

            if (
                term
                <=
                max(
                    1e-16,
                    (
                        tail
                        *
                        1e-14
                    ),
                )
            ):

                break

        return max(
            0.0,
            min(
                1.0,
                tail,
            ),
        )

    # ==========================================================
    # Surprise
    # ==========================================================

    @staticmethod
    def _surprise_score(
        p_value: float,
    ) -> float:
        """
        Statistical surprise:

            -log10(p)

        Capped at 300 to keep the result finite when
        p == 0 due to a zero historical baseline.
        """

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
    # Ordering
    # ==========================================================

    @staticmethod
    def _scope_rank(
        scope: TemporalBurstScope,
    ) -> int:

        return {
            TemporalBurstScope.GLOBAL:
                0,

            TemporalBurstScope.ENTITY:
                1,

            TemporalBurstScope.EVENT_TYPE:
                2,
        }[
            scope
        ]