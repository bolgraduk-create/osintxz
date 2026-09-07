"""
Temporal correlation analysis.

Measures statistical co-variation between temporal
activity series produced from Phase 4.1 features.

Pipeline:

TemporalFeatureResult
    ↓
fixed-duration windows
    ↓
Entity activity series
Event-type activity series
    ↓
Pearson correlation
    ↓
TemporalCorrelationResult

Temporal semantics:

- windows are fixed-duration absolute-time windows
- window boundaries are aligned to Unix epoch
- bin starts are reported in UTC
- activity counts remain case-scoped
- only occurrence timestamps from Phase 4.1 are used

Important:

Temporal correlation describes statistical co-variation.

It is NOT:

- causation
- proof of coordination
- identity evidence
- relationship evidence
- Entity Resolution evidence

Does NOT:

- query the database
- write to the database
- modify TimelineEvent
- use created_at
- perform lagged correlation
- detect bursts
- detect change points
- perform anomaly detection
"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import (
    datetime,
    timezone,
)

from enum import Enum

from itertools import combinations

from math import (
    floor,
    isfinite,
    sqrt,
)

from uuid import UUID

from app.analysis.temporal_feature_extraction import (
    TemporalFeatureResult,
)


# ==========================================================
# Series kind
# ==========================================================


class TemporalSeriesKind(
    str,
    Enum,
):
    """
    Supported temporal activity-series dimensions.
    """

    ENTITY = "entity"

    EVENT_TYPE = "event_type"


# ==========================================================
# Correlation status
# ==========================================================


class TemporalCorrelationStatus(
    str,
    Enum,
):
    """
    Mathematical availability of one correlation.
    """

    VALID = "valid"

    INSUFFICIENT_WINDOWS = (
        "insufficient_windows"
    )

    ZERO_VARIANCE = (
        "zero_variance"
    )


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalCorrelationConfig:
    """
    Temporal correlation configuration.

    window_seconds:

        Width of one fixed activity window.

        Default:
            3600 seconds = 1 hour.

    minimum_windows:

        Minimum number of windows required before a
        Pearson coefficient is considered meaningful.

        Pearson can mathematically be calculated from
        two observations, but default 3 is deliberately
        more conservative.

    include_entity_correlations:

        Build pairwise Entity activity correlations.

    include_event_type_correlations:

        Build pairwise event-type activity correlations.
    """

    window_seconds: int = 3600

    minimum_windows: int = 3

    include_entity_correlations: bool = True

    include_event_type_correlations: bool = True

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.window_seconds,
                int,
            )
            or self.window_seconds <= 0
        ):

            raise ValueError(
                "window_seconds must be "
                "a positive integer."
            )

        if (
            not isinstance(
                self.minimum_windows,
                int,
            )
            or self.minimum_windows < 2
        ):

            raise ValueError(
                "minimum_windows must be "
                "an integer >= 2."
            )

        if not isinstance(
            self.include_entity_correlations,
            bool,
        ):

            raise TypeError(
                "include_entity_correlations "
                "must be bool."
            )

        if not isinstance(
            self.include_event_type_correlations,
            bool,
        ):

            raise TypeError(
                "include_event_type_correlations "
                "must be bool."
            )


# ==========================================================
# Activity series
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalActivitySeries:
    """
    One temporal activity-count vector.

    Examples:

        Entity A:
            (1, 0, 3, 2)

        event type MESSAGE:
            (4, 1, 8, 5)
    """

    kind: TemporalSeriesKind

    series_id: str

    counts: tuple[
        int,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.kind,
            TemporalSeriesKind,
        ):

            raise TypeError(
                "kind must be TemporalSeriesKind."
            )

        if (
            not isinstance(
                self.series_id,
                str,
            )
            or not self.series_id.strip()
        ):

            raise ValueError(
                "series_id cannot be empty."
            )

        normalized_id = (
            self.series_id.strip()
        )

        if (
            self.kind
            ==
            TemporalSeriesKind.EVENT_TYPE
        ):

            normalized_id = (
                normalized_id.lower()
            )

        if (
            self.kind
            ==
            TemporalSeriesKind.ENTITY
        ):

            # Validate canonical UUID representation.
            entity_id = UUID(
                normalized_id
            )

            normalized_id = str(
                entity_id
            )

        object.__setattr__(
            self,
            "series_id",
            normalized_id,
        )

        if not isinstance(
            self.counts,
            tuple,
        ):

            raise TypeError(
                "counts must be a tuple."
            )

        normalized_counts: list[
            int
        ] = []

        for count in self.counts:

            if (
                not isinstance(
                    count,
                    int,
                )
                or count < 0
            ):

                raise ValueError(
                    "Activity counts must be "
                    "non-negative integers."
                )

            normalized_counts.append(
                count
            )

        object.__setattr__(
            self,
            "counts",
            tuple(
                normalized_counts
            ),
        )

    # ==========================================================
    # Diagnostics
    # ==========================================================

    @property
    def window_count(
        self,
    ) -> int:

        return len(
            self.counts
        )

    @property
    def total_events(
        self,
    ) -> int:

        return sum(
            self.counts
        )

    @property
    def active_window_count(
        self,
    ) -> int:

        return sum(
            1
            for count
            in self.counts
            if count > 0
        )

    @property
    def inactive_window_count(
        self,
    ) -> int:

        return (
            self.window_count
            -
            self.active_window_count
        )

    @property
    def has_variance(
        self,
    ) -> bool:
        """
        Whether the activity vector changes over time.
        """

        if len(
            self.counts
        ) < 2:

            return False

        return (
            len(
                set(
                    self.counts
                )
            )
            >
            1
        )


# ==========================================================
# Pair result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalCorrelationPair:
    """
    Pearson correlation between two temporal series.

    coefficient:

        [-1, 1] when status == VALID

        None when correlation is mathematically
        unavailable.

    shared_active_windows:

        Number of windows where BOTH series have at
        least one event.

        This is a diagnostic, not part of the Pearson
        coefficient.
    """

    kind: TemporalSeriesKind

    first_series_id: str

    second_series_id: str

    coefficient: (
        float
        | None
    )

    status: TemporalCorrelationStatus

    window_count: int

    first_active_windows: int

    second_active_windows: int

    shared_active_windows: int

    first_total_events: int

    second_total_events: int

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.kind,
            TemporalSeriesKind,
        ):

            raise TypeError(
                "kind must be TemporalSeriesKind."
            )

        first_id = self._normalize_series_id(
            self.first_series_id
        )

        second_id = self._normalize_series_id(
            self.second_series_id
        )

        if first_id == second_id:

            raise ValueError(
                "Correlation pair requires "
                "two different series."
            )

        if first_id > second_id:

            raise ValueError(
                "Correlation pair IDs must be "
                "stored canonically."
            )

        object.__setattr__(
            self,
            "first_series_id",
            first_id,
        )

        object.__setattr__(
            self,
            "second_series_id",
            second_id,
        )

        if not isinstance(
            self.status,
            TemporalCorrelationStatus,
        ):

            raise TypeError(
                "status must be "
                "TemporalCorrelationStatus."
            )

        for field_name in (
            "window_count",
            "first_active_windows",
            "second_active_windows",
            "shared_active_windows",
            "first_total_events",
            "second_total_events",
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
            self.first_active_windows
            >
            self.window_count
            or
            self.second_active_windows
            >
            self.window_count
            or
            self.shared_active_windows
            >
            self.window_count
        ):

            raise ValueError(
                "Active-window count cannot "
                "exceed window_count."
            )

        if (
            self.shared_active_windows
            >
            min(
                self.first_active_windows,
                self.second_active_windows,
            )
        ):

            raise ValueError(
                "shared_active_windows cannot exceed "
                "either series' active-window count."
            )

        if (
            self.status
            ==
            TemporalCorrelationStatus.VALID
        ):

            if self.coefficient is None:

                raise ValueError(
                    "VALID correlation requires "
                    "coefficient."
                )

            coefficient = float(
                self.coefficient
            )

            if (
                not isfinite(
                    coefficient
                )
                or not (
                    -1.0
                    <= coefficient
                    <= 1.0
                )
            ):

                raise ValueError(
                    "Correlation coefficient must "
                    "be between -1.0 and 1.0."
                )

            object.__setattr__(
                self,
                "coefficient",
                coefficient,
            )

        else:

            if self.coefficient is not None:

                raise ValueError(
                    "Unavailable correlation must "
                    "have coefficient=None."
                )

    # ==========================================================
    # Series ID normalization
    # ==========================================================

    def _normalize_series_id(
        self,
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
                "Correlation series ID "
                "cannot be empty."
            )

        normalized = (
            value.strip()
        )

        if (
            self.kind
            ==
            TemporalSeriesKind.ENTITY
        ):

            normalized = str(
                UUID(
                    normalized
                )
            )

        else:

            normalized = (
                normalized.lower()
            )

        return normalized

    # ==========================================================
    # Diagnostics
    # ==========================================================

    @property
    def is_valid(
        self,
    ) -> bool:

        return (
            self.status
            ==
            TemporalCorrelationStatus.VALID
        )

    @property
    def absolute_coefficient(
        self,
    ) -> (
        float
        | None
    ):

        if self.coefficient is None:

            return None

        return abs(
            self.coefficient
        )

    @property
    def shared_activity_rate(
        self,
    ) -> float:
        """
        Fraction of all windows in which both series
        are active.

        Kept separate from Pearson correlation.
        """

        if self.window_count == 0:

            return 0.0

        return (
            self.shared_active_windows
            /
            self.window_count
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalCorrelationResult:
    """
    Complete Phase 4.2 temporal-correlation result.
    """

    case_id: (
        UUID
        | None
    )

    window_seconds: int

    minimum_windows: int

    window_starts_utc: tuple[
        datetime,
        ...,
    ]

    entity_series: tuple[
        TemporalActivitySeries,
        ...,
    ]

    event_type_series: tuple[
        TemporalActivitySeries,
        ...,
    ]

    entity_correlations: tuple[
        TemporalCorrelationPair,
        ...,
    ]

    event_type_correlations: tuple[
        TemporalCorrelationPair,
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

        if (
            not isinstance(
                self.minimum_windows,
                int,
            )
            or self.minimum_windows < 2
        ):

            raise ValueError(
                "minimum_windows must be >= 2."
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
                    "window_starts_utc must contain "
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
                    "Window timestamps must "
                    "be timezone-aware."
                )

        expected_window_count = len(
            self.window_starts_utc
        )

        for series_group in (
            self.entity_series,
            self.event_type_series,
        ):

            if not isinstance(
                series_group,
                tuple,
            ):

                raise TypeError(
                    "Temporal series collections "
                    "must be tuples."
                )

            seen_ids: set[
                str
            ] = set()

            for series in series_group:

                if not isinstance(
                    series,
                    TemporalActivitySeries,
                ):

                    raise TypeError(
                        "Series collection contains "
                        "invalid object."
                    )

                if (
                    series.window_count
                    !=
                    expected_window_count
                ):

                    raise ValueError(
                        "Temporal series window "
                        "count mismatch."
                    )

                if (
                    series.series_id
                    in seen_ids
                ):

                    raise ValueError(
                        "Duplicate temporal series."
                    )

                seen_ids.add(
                    series.series_id
                )

        self._validate_correlations(
            self.entity_correlations,
            expected_kind=(
                TemporalSeriesKind.ENTITY
            ),
            window_count=(
                expected_window_count
            ),
        )

        self._validate_correlations(
            self.event_type_correlations,
            expected_kind=(
                TemporalSeriesKind.EVENT_TYPE
            ),
            window_count=(
                expected_window_count
            ),
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_correlations(
        correlations: tuple[
            TemporalCorrelationPair,
            ...,
        ],
        *,
        expected_kind: TemporalSeriesKind,
        window_count: int,
    ) -> None:

        if not isinstance(
            correlations,
            tuple,
        ):

            raise TypeError(
                "correlations must be tuple."
            )

        seen_pairs: set[
            tuple[
                str,
                str,
            ]
        ] = set()

        for correlation in correlations:

            if not isinstance(
                correlation,
                TemporalCorrelationPair,
            ):

                raise TypeError(
                    "correlations must contain "
                    "TemporalCorrelationPair."
                )

            if (
                correlation.kind
                !=
                expected_kind
            ):

                raise ValueError(
                    "Correlation kind mismatch."
                )

            if (
                correlation.window_count
                !=
                window_count
            ):

                raise ValueError(
                    "Correlation window-count "
                    "mismatch."
                )

            pair = (
                correlation.first_series_id,
                correlation.second_series_id,
            )

            if pair in seen_pairs:

                raise ValueError(
                    "Duplicate temporal "
                    "correlation pair."
                )

            seen_pairs.add(
                pair
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
    def entity_series_count(
        self,
    ) -> int:

        return len(
            self.entity_series
        )

    @property
    def event_type_series_count(
        self,
    ) -> int:

        return len(
            self.event_type_series
        )

    # ==========================================================
    # Series lookup
    # ==========================================================

    def get_entity_series(
        self,
        entity_id: UUID,
    ) -> TemporalActivitySeries:

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

        for series in (
            self.entity_series
        ):

            if (
                series.series_id
                ==
                target
            ):

                return series

        raise KeyError(
            "Entity temporal series not found."
        )

    def get_event_type_series(
        self,
        event_type: str,
    ) -> TemporalActivitySeries:

        target = (
            str(
                event_type
            )
            .strip()
            .lower()
        )

        for series in (
            self.event_type_series
        ):

            if (
                series.series_id
                ==
                target
            ):

                return series

        raise KeyError(
            "Event-type temporal series "
            "not found."
        )

    # ==========================================================
    # Correlation lookup
    # ==========================================================

    def get_entity_correlation(
        self,
        first_entity_id: UUID,
        second_entity_id: UUID,
    ) -> TemporalCorrelationPair:

        if not isinstance(
            first_entity_id,
            UUID,
        ):

            raise TypeError(
                "first_entity_id must be UUID."
            )

        if not isinstance(
            second_entity_id,
            UUID,
        ):

            raise TypeError(
                "second_entity_id must be UUID."
            )

        first, second = sorted(
            (
                str(
                    first_entity_id
                ),
                str(
                    second_entity_id
                ),
            )
        )

        return self._get_correlation(
            self.entity_correlations,
            first,
            second,
        )

    def get_event_type_correlation(
        self,
        first_event_type: str,
        second_event_type: str,
    ) -> TemporalCorrelationPair:

        first, second = sorted(
            (
                str(
                    first_event_type
                )
                .strip()
                .lower(),
                str(
                    second_event_type
                )
                .strip()
                .lower(),
            )
        )

        return self._get_correlation(
            self.event_type_correlations,
            first,
            second,
        )

    @staticmethod
    def _get_correlation(
        correlations: tuple[
            TemporalCorrelationPair,
            ...,
        ],
        first: str,
        second: str,
    ) -> TemporalCorrelationPair:

        if first == second:

            raise ValueError(
                "Correlation lookup requires "
                "two different series."
            )

        for correlation in correlations:

            if (
                correlation.first_series_id
                ==
                first
                and
                correlation.second_series_id
                ==
                second
            ):

                return correlation

        raise KeyError(
            "Temporal correlation pair "
            "not found."
        )

    # ==========================================================
    # Ranking
    # ==========================================================

    def top_entity_correlations(
        self,
        limit: int = 10,
        *,
        absolute: bool = True,
    ) -> tuple[
        TemporalCorrelationPair,
        ...,
    ]:

        return self._top_correlations(
            self.entity_correlations,
            limit=limit,
            absolute=absolute,
        )

    def top_event_type_correlations(
        self,
        limit: int = 10,
        *,
        absolute: bool = True,
    ) -> tuple[
        TemporalCorrelationPair,
        ...,
    ]:

        return self._top_correlations(
            self.event_type_correlations,
            limit=limit,
            absolute=absolute,
        )

    @staticmethod
    def _top_correlations(
        correlations: tuple[
            TemporalCorrelationPair,
            ...,
        ],
        *,
        limit: int,
        absolute: bool,
    ) -> tuple[
        TemporalCorrelationPair,
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
                "limit must be a "
                "non-negative integer."
            )

        if not isinstance(
            absolute,
            bool,
        ):

            raise TypeError(
                "absolute must be bool."
            )

        valid = [
            item
            for item
            in correlations
            if item.is_valid
        ]

        if absolute:

            ordered = sorted(
                valid,
                key=lambda item: (
                    -abs(
                        item.coefficient
                    ),
                    -item.coefficient,
                    item.first_series_id,
                    item.second_series_id,
                ),
            )

        else:

            ordered = sorted(
                valid,
                key=lambda item: (
                    -item.coefficient,
                    item.first_series_id,
                    item.second_series_id,
                ),
            )

        return tuple(
            ordered[
                :limit
            ]
        )


# ==========================================================
# Service
# ==========================================================


class TemporalCorrelationService:
    """
    Pure temporal correlation service.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        features: TemporalFeatureResult,
        config: (
            TemporalCorrelationConfig
            | None
        ) = None,
    ) -> TemporalCorrelationResult:
        """
        Build activity series and calculate pairwise
        zero-lag Pearson correlations.

        No database writes are performed.
        """

        if not isinstance(
            features,
            TemporalFeatureResult,
        ):

            raise TypeError(
                "features must be "
                "TemporalFeatureResult."
            )

        config = (
            config
            or
            TemporalCorrelationConfig()
        )

        if not isinstance(
            config,
            TemporalCorrelationConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalCorrelationConfig."
            )

        (
            window_starts,
            observation_window_indices,
        ) = self._build_windows(
            features,
            window_seconds=(
                config.window_seconds
            ),
        )

        entity_series = (
            self._build_entity_series(
                features,
                observation_window_indices=(
                    observation_window_indices
                ),
                window_count=len(
                    window_starts
                ),
            )
        )

        event_type_series = (
            self._build_event_type_series(
                features,
                observation_window_indices=(
                    observation_window_indices
                ),
                window_count=len(
                    window_starts
                ),
            )
        )

        if (
            config
            .include_entity_correlations
        ):

            entity_correlations = (
                self._build_correlations(
                    entity_series,
                    minimum_windows=(
                        config.minimum_windows
                    ),
                )
            )

        else:

            entity_correlations = ()

        if (
            config
            .include_event_type_correlations
        ):

            event_type_correlations = (
                self._build_correlations(
                    event_type_series,
                    minimum_windows=(
                        config.minimum_windows
                    ),
                )
            )

        else:

            event_type_correlations = ()

        return TemporalCorrelationResult(
            case_id=(
                features.case_id
            ),
            window_seconds=(
                config.window_seconds
            ),
            minimum_windows=(
                config.minimum_windows
            ),
            window_starts_utc=(
                window_starts
            ),
            entity_series=(
                entity_series
            ),
            event_type_series=(
                event_type_series
            ),
            entity_correlations=(
                entity_correlations
            ),
            event_type_correlations=(
                event_type_correlations
            ),
        )

    # ==========================================================
    # Window construction
    # ==========================================================

    @staticmethod
    def _build_windows(
        features: TemporalFeatureResult,
        *,
        window_seconds: int,
    ) -> tuple[
        tuple[
            datetime,
            ...,
        ],
        tuple[
            int,
            ...,
        ],
    ]:
        """
        Build epoch-aligned fixed-duration windows.

        Absolute epoch alignment prevents the first event
        from arbitrarily changing all bucket boundaries.

        Bin starts are returned in UTC.
        """

        observations = (
            features.observations
        )

        if not observations:

            return (
                (),
                (),
            )

        first_epoch = (
            observations[
                0
            ]
            .timestamp
            .timestamp()
        )

        first_bin_number = floor(
            first_epoch
            /
            window_seconds
        )

        bin_numbers: list[
            int
        ] = []

        for observation in observations:

            epoch_seconds = (
                observation
                .timestamp
                .timestamp()
            )

            bin_number = floor(
                epoch_seconds
                /
                window_seconds
            )

            bin_numbers.append(
                bin_number
            )

        last_bin_number = max(
            bin_numbers
        )

        window_count = (
            last_bin_number
            -
            first_bin_number
            +
            1
        )

        window_starts = tuple(
            datetime.fromtimestamp(
                (
                    first_bin_number
                    +
                    offset
                )
                *
                window_seconds,
                tz=timezone.utc,
            )
            for offset
            in range(
                window_count
            )
        )

        indices = tuple(
            bin_number
            -
            first_bin_number
            for bin_number
            in bin_numbers
        )

        return (
            window_starts,
            indices,
        )

    # ==========================================================
    # Entity activity series
    # ==========================================================

    @staticmethod
    def _build_entity_series(
        features: TemporalFeatureResult,
        *,
        observation_window_indices: tuple[
            int,
            ...,
        ],
        window_count: int,
    ) -> tuple[
        TemporalActivitySeries,
        ...,
    ]:

        counters: dict[
            UUID,
            list[
                int
            ],
        ] = {}

        for (
            observation,
            window_index,
        ) in zip(
            features.observations,
            observation_window_indices,
        ):

            entity_id = (
                observation.entity_id
            )

            if entity_id is None:

                continue

            counts = counters.get(
                entity_id
            )

            if counts is None:

                counts = [
                    0
                    for _
                    in range(
                        window_count
                    )
                ]

                counters[
                    entity_id
                ] = counts

            counts[
                window_index
            ] += 1

        result = [
            TemporalActivitySeries(
                kind=(
                    TemporalSeriesKind.ENTITY
                ),
                series_id=str(
                    entity_id
                ),
                counts=tuple(
                    counts
                ),
            )
            for entity_id, counts
            in counters.items()
        ]

        result.sort(
            key=lambda item: (
                item.series_id
            )
        )

        return tuple(
            result
        )

    # ==========================================================
    # Event-type activity series
    # ==========================================================

    @staticmethod
    def _build_event_type_series(
        features: TemporalFeatureResult,
        *,
        observation_window_indices: tuple[
            int,
            ...,
        ],
        window_count: int,
    ) -> tuple[
        TemporalActivitySeries,
        ...,
    ]:

        counters: dict[
            str,
            list[
                int
            ],
        ] = {}

        for (
            observation,
            window_index,
        ) in zip(
            features.observations,
            observation_window_indices,
        ):

            event_type = (
                observation.event_type
                .strip()
                .lower()
            )

            counts = counters.get(
                event_type
            )

            if counts is None:

                counts = [
                    0
                    for _
                    in range(
                        window_count
                    )
                ]

                counters[
                    event_type
                ] = counts

            counts[
                window_index
            ] += 1

        result = [
            TemporalActivitySeries(
                kind=(
                    TemporalSeriesKind
                    .EVENT_TYPE
                ),
                series_id=(
                    event_type
                ),
                counts=tuple(
                    counts
                ),
            )
            for event_type, counts
            in counters.items()
        ]

        result.sort(
            key=lambda item: (
                item.series_id
            )
        )

        return tuple(
            result
        )

    # ==========================================================
    # Pairwise correlations
    # ==========================================================

    def _build_correlations(
        self,
        series: tuple[
            TemporalActivitySeries,
            ...,
        ],
        *,
        minimum_windows: int,
    ) -> tuple[
        TemporalCorrelationPair,
        ...,
    ]:

        correlations: list[
            TemporalCorrelationPair
        ] = []

        for (
            first,
            second,
        ) in combinations(
            series,
            2,
        ):

            correlations.append(
                self._correlate_pair(
                    first,
                    second,
                    minimum_windows=(
                        minimum_windows
                    ),
                )
            )

        correlations.sort(
            key=lambda item: (
                item.first_series_id,
                item.second_series_id,
            )
        )

        return tuple(
            correlations
        )

    # ==========================================================
    # One correlation
    # ==========================================================

    def _correlate_pair(
        self,
        first: TemporalActivitySeries,
        second: TemporalActivitySeries,
        *,
        minimum_windows: int,
    ) -> TemporalCorrelationPair:

        if (
            first.kind
            !=
            second.kind
        ):

            raise ValueError(
                "Cannot correlate different "
                "temporal series kinds."
            )

        if (
            first.window_count
            !=
            second.window_count
        ):

            raise ValueError(
                "Temporal series window counts "
                "must match."
            )

        first_id, second_id = sorted(
            (
                first.series_id,
                second.series_id,
            )
        )

        if (
            first_id
            !=
            first.series_id
        ):

            first, second = (
                second,
                first,
            )

        window_count = (
            first.window_count
        )

        shared_active_windows = sum(
            1
            for (
                first_count,
                second_count,
            )
            in zip(
                first.counts,
                second.counts,
            )
            if (
                first_count > 0
                and
                second_count > 0
            )
        )

        if (
            window_count
            <
            minimum_windows
        ):

            return (
                TemporalCorrelationPair(
                    kind=first.kind,
                    first_series_id=(
                        first.series_id
                    ),
                    second_series_id=(
                        second.series_id
                    ),
                    coefficient=None,
                    status=(
                        TemporalCorrelationStatus
                        .INSUFFICIENT_WINDOWS
                    ),
                    window_count=(
                        window_count
                    ),
                    first_active_windows=(
                        first
                        .active_window_count
                    ),
                    second_active_windows=(
                        second
                        .active_window_count
                    ),
                    shared_active_windows=(
                        shared_active_windows
                    ),
                    first_total_events=(
                        first.total_events
                    ),
                    second_total_events=(
                        second.total_events
                    ),
                )
            )

        if (
            not first.has_variance
            or
            not second.has_variance
        ):

            return (
                TemporalCorrelationPair(
                    kind=first.kind,
                    first_series_id=(
                        first.series_id
                    ),
                    second_series_id=(
                        second.series_id
                    ),
                    coefficient=None,
                    status=(
                        TemporalCorrelationStatus
                        .ZERO_VARIANCE
                    ),
                    window_count=(
                        window_count
                    ),
                    first_active_windows=(
                        first
                        .active_window_count
                    ),
                    second_active_windows=(
                        second
                        .active_window_count
                    ),
                    shared_active_windows=(
                        shared_active_windows
                    ),
                    first_total_events=(
                        first.total_events
                    ),
                    second_total_events=(
                        second.total_events
                    ),
                )
            )

        coefficient = (
            self._pearson(
                first.counts,
                second.counts,
            )
        )

        return (
            TemporalCorrelationPair(
                kind=first.kind,
                first_series_id=(
                    first.series_id
                ),
                second_series_id=(
                    second.series_id
                ),
                coefficient=(
                    coefficient
                ),
                status=(
                    TemporalCorrelationStatus.VALID
                ),
                window_count=(
                    window_count
                ),
                first_active_windows=(
                    first
                    .active_window_count
                ),
                second_active_windows=(
                    second
                    .active_window_count
                ),
                shared_active_windows=(
                    shared_active_windows
                ),
                first_total_events=(
                    first.total_events
                ),
                second_total_events=(
                    second.total_events
                ),
            )
        )

    # ==========================================================
    # Pearson
    # ==========================================================

    @staticmethod
    def _pearson(
        first: tuple[
            int,
            ...,
        ],
        second: tuple[
            int,
            ...,
        ],
    ) -> float:
        """
        Exact zero-lag Pearson product-moment
        correlation over activity counts.
        """

        if len(
            first
        ) != len(
            second
        ):

            raise ValueError(
                "Pearson vectors must have "
                "equal length."
            )

        if len(
            first
        ) < 2:

            raise ValueError(
                "Pearson requires at least "
                "two observations."
            )

        count = len(
            first
        )

        first_mean = (
            sum(
                first
            )
            /
            count
        )

        second_mean = (
            sum(
                second
            )
            /
            count
        )

        covariance_numerator = 0.0

        first_square_sum = 0.0

        second_square_sum = 0.0

        for (
            first_value,
            second_value,
        ) in zip(
            first,
            second,
        ):

            first_delta = (
                first_value
                -
                first_mean
            )

            second_delta = (
                second_value
                -
                second_mean
            )

            covariance_numerator += (
                first_delta
                *
                second_delta
            )

            first_square_sum += (
                first_delta
                *
                first_delta
            )

            second_square_sum += (
                second_delta
                *
                second_delta
            )

        denominator = sqrt(
            first_square_sum
            *
            second_square_sum
        )

        if denominator <= 0.0:

            raise ValueError(
                "Pearson denominator is zero."
            )

        coefficient = (
            covariance_numerator
            /
            denominator
        )

        # Floating-point guard.
        coefficient = max(
            -1.0,
            min(
                1.0,
                coefficient,
            ),
        )

        if not isfinite(
            coefficient
        ):

            raise ValueError(
                "Pearson result is not finite."
            )

        return coefficient