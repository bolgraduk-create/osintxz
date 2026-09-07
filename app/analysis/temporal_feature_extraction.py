"""
Temporal feature extraction.

Builds a deterministic mathematical representation of
an investigation timeline.

Canonical production input:

    app.models.timeline_event.TimelineEvent

Temporal semantics:

    TimelineEvent.event_time
        = occurrence time of the event

    TimelineEvent.created_at
        = persistence / provenance time
        = NOT used as event occurrence time

Pipeline:

TimelineEvent
    ↓
timestamp normalization
    ↓
TemporalObservation
    ↓
chronological sequence
    ↓
TemporalFeatureResult

Responsibilities:

- parse event occurrence timestamps
- normalize timezones explicitly
- preserve malformed timestamp diagnostics
- build deterministic chronological observations
- calculate inter-event intervals
- calculate activity span and event rates
- calculate hour-of-day distribution
- calculate weekday distribution
- calculate event-type distribution
- calculate Entity activity distribution
- detect simultaneous timestamps

Does NOT:

- query the database
- write to the database
- use created_at as occurrence time
- detect bursts
- calculate temporal correlation
- detect change points
- perform anomaly detection
"""

from __future__ import annotations

from collections import Counter

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
    tzinfo,
)

from math import (
    isfinite,
)

from statistics import (
    mean,
    median,
)

from typing import Any

from uuid import UUID

from app.models.timeline_event import (
    TimelineEvent,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalFeatureExtractionConfig:
    """
    Temporal feature configuration.

    analysis_timezone:

        Every accepted timestamp is converted to this
        timezone before extracting hour / weekday
        features.

    naive_timezone:

        Timezone assumed for ISO timestamps that contain
        no timezone information.

        Default UTC preserves compatibility with existing
        naive timeline strings while making the assumption
        explicit and observable through diagnostics.

        Set to None to reject naive timestamps.

    strict_invalid_timestamps:

        False:
            malformed timestamps are recorded and skipped.

        True:
            first malformed timestamp raises ValueError.
    """

    analysis_timezone: tzinfo = field(
        default=timezone.utc
    )

    naive_timezone: (
        tzinfo
        | None
    ) = field(
        default=timezone.utc
    )

    strict_invalid_timestamps: bool = False

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.analysis_timezone,
            tzinfo,
        ):

            raise TypeError(
                "analysis_timezone must be tzinfo."
            )

        if (
            self.naive_timezone
            is not None
            and
            not isinstance(
                self.naive_timezone,
                tzinfo,
            )
        ):

            raise TypeError(
                "naive_timezone must be "
                "tzinfo or None."
            )

        if not isinstance(
            self.strict_invalid_timestamps,
            bool,
        ):

            raise TypeError(
                "strict_invalid_timestamps "
                "must be bool."
            )


# ==========================================================
# Rejected timestamp
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RejectedTemporalTimestamp:
    """
    One TimelineEvent rejected because its occurrence
    timestamp could not safely enter the temporal model.
    """

    event_id: UUID

    raw_timestamp: str

    reason: str

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.event_id,
            UUID,
        ):

            raise TypeError(
                "event_id must be UUID."
            )

        if not isinstance(
            self.raw_timestamp,
            str,
        ):

            raise TypeError(
                "raw_timestamp must be string."
            )

        if (
            not isinstance(
                self.reason,
                str,
            )
            or
            not self.reason.strip()
        ):

            raise ValueError(
                "reason cannot be empty."
            )

        object.__setattr__(
            self,
            "reason",
            self.reason.strip(),
        )


# ==========================================================
# Normalization diagnostics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalNormalizationDiagnostics:
    """
    Timestamp normalization diagnostics.
    """

    input_event_count: int

    accepted_event_count: int

    rejected_event_count: int

    assumed_timezone_count: int

    rejected_timestamps: tuple[
        RejectedTemporalTimestamp,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "input_event_count",
            "accepted_event_count",
            "rejected_event_count",
            "assumed_timezone_count",
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
            self.accepted_event_count
            +
            self.rejected_event_count
            !=
            self.input_event_count
        ):

            raise ValueError(
                "Accepted + rejected count must "
                "equal input count."
            )

        if (
            self.assumed_timezone_count
            >
            self.accepted_event_count
        ):

            raise ValueError(
                "assumed_timezone_count cannot "
                "exceed accepted_event_count."
            )

        if not isinstance(
            self.rejected_timestamps,
            tuple,
        ):

            raise TypeError(
                "rejected_timestamps must "
                "be a tuple."
            )

        if (
            len(
                self.rejected_timestamps
            )
            !=
            self.rejected_event_count
        ):

            raise ValueError(
                "Rejected timestamp diagnostics "
                "count mismatch."
            )


# ==========================================================
# Normalized observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalObservation:
    """
    One normalized temporal event.

    timestamp is always timezone-aware.
    """

    event_id: UUID

    case_id: UUID

    entity_id: (
        UUID
        | None
    )

    event_type: str

    timestamp: datetime

    raw_timestamp: str

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.event_id,
            UUID,
        ):

            raise TypeError(
                "event_id must be UUID."
            )

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if (
            self.entity_id
            is not None
            and
            not isinstance(
                self.entity_id,
                UUID,
            )
        ):

            raise TypeError(
                "entity_id must be UUID or None."
            )

        if (
            not isinstance(
                self.event_type,
                str,
            )
            or
            not self.event_type.strip()
        ):

            raise ValueError(
                "event_type cannot be empty."
            )

        normalized_type = (
            self.event_type
            .strip()
            .lower()
        )

        object.__setattr__(
            self,
            "event_type",
            normalized_type,
        )

        if not isinstance(
            self.timestamp,
            datetime,
        ):

            raise TypeError(
                "timestamp must be datetime."
            )

        if (
            self.timestamp.tzinfo
            is None
            or
            self.timestamp.utcoffset()
            is None
        ):

            raise ValueError(
                "TemporalObservation timestamp "
                "must be timezone-aware."
            )

        if not isinstance(
            self.raw_timestamp,
            str,
        ):

            raise TypeError(
                "raw_timestamp must be string."
            )


# ==========================================================
# Interval statistics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalIntervalStatistics:
    """
    Statistics over consecutive event intervals.
    """

    count: int

    minimum_seconds: (
        float
        | None
    )

    maximum_seconds: (
        float
        | None
    )

    mean_seconds: (
        float
        | None
    )

    median_seconds: (
        float
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        if (
            not isinstance(
                self.count,
                int,
            )
            or self.count < 0
        ):

            raise ValueError(
                "count must be non-negative."
            )

        values = (
            self.minimum_seconds,
            self.maximum_seconds,
            self.mean_seconds,
            self.median_seconds,
        )

        if self.count == 0:

            if any(
                value is not None
                for value
                in values
            ):

                raise ValueError(
                    "Empty interval statistics "
                    "must contain None values."
                )

            return

        for value in values:

            if value is None:

                raise ValueError(
                    "Non-empty interval statistics "
                    "cannot contain None."
                )

            numeric = float(
                value
            )

            if (
                not isfinite(
                    numeric
                )
                or numeric < 0.0
            ):

                raise ValueError(
                    "Interval statistics must "
                    "be finite and non-negative."
                )


# ==========================================================
# Feature result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class TemporalFeatureResult:
    """
    Complete Phase 4.1 temporal feature result.
    """

    case_id: (
        UUID
        | None
    )

    observations: tuple[
        TemporalObservation,
        ...,
    ]

    diagnostics: (
        TemporalNormalizationDiagnostics
    )

    first_timestamp: (
        datetime
        | None
    )

    last_timestamp: (
        datetime
        | None
    )

    span_seconds: float

    intervals_seconds: tuple[
        float,
        ...,
    ]

    interval_statistics: (
        TemporalIntervalStatistics
    )

    unique_timestamp_count: int

    simultaneous_event_count: int

    events_per_hour: (
        float
        | None
    )

    events_per_day: (
        float
        | None
    )

    hour_counts: tuple[
        int,
        ...,
    ]

    weekday_counts: tuple[
        int,
        ...,
    ]

    event_type_counts: tuple[
        tuple[
            str,
            int,
        ],
        ...,
    ]

    entity_event_counts: tuple[
        tuple[
            UUID,
            int,
        ],
        ...,
    ]

    unassigned_entity_event_count: int

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

        if not isinstance(
            self.observations,
            tuple,
        ):

            raise TypeError(
                "observations must be a tuple."
            )

        if not isinstance(
            self.diagnostics,
            TemporalNormalizationDiagnostics,
        ):

            raise TypeError(
                "diagnostics must be "
                "TemporalNormalizationDiagnostics."
            )

        if (
            len(
                self.observations
            )
            !=
            self.diagnostics
            .accepted_event_count
        ):

            raise ValueError(
                "Observation count does not match "
                "normalization diagnostics."
            )

        if not isinstance(
            self.span_seconds,
            (int, float),
        ):

            raise TypeError(
                "span_seconds must be numeric."
            )

        span = float(
            self.span_seconds
        )

        if (
            not isfinite(
                span
            )
            or span < 0.0
        ):

            raise ValueError(
                "span_seconds must be finite "
                "and non-negative."
            )

        object.__setattr__(
            self,
            "span_seconds",
            span,
        )

        if (
            len(
                self.hour_counts
            )
            != 24
        ):

            raise ValueError(
                "hour_counts must contain "
                "24 entries."
            )

        if (
            len(
                self.weekday_counts
            )
            != 7
        ):

            raise ValueError(
                "weekday_counts must contain "
                "7 entries."
            )

        if (
            sum(
                self.hour_counts
            )
            !=
            len(
                self.observations
            )
        ):

            raise ValueError(
                "hour_counts coverage mismatch."
            )

        if (
            sum(
                self.weekday_counts
            )
            !=
            len(
                self.observations
            )
        ):

            raise ValueError(
                "weekday_counts coverage mismatch."
            )

        if (
            self.unique_timestamp_count
            < 0
            or
            self.unique_timestamp_count
            >
            len(
                self.observations
            )
        ):

            raise ValueError(
                "Invalid unique_timestamp_count."
            )

        if (
            self.simultaneous_event_count
            !=
            (
                len(
                    self.observations
                )
                -
                self.unique_timestamp_count
            )
        ):

            raise ValueError(
                "simultaneous_event_count mismatch."
            )

        if (
            len(
                self.intervals_seconds
            )
            !=
            max(
                0,
                len(
                    self.observations
                )
                -
                1,
            )
        ):

            raise ValueError(
                "Interval count does not match "
                "observation count."
            )

        if (
            self.interval_statistics.count
            !=
            len(
                self.intervals_seconds
            )
        ):

            raise ValueError(
                "Interval statistics count mismatch."
            )

        for rate in (
            self.events_per_hour,
            self.events_per_day,
        ):

            if rate is None:

                continue

            numeric = float(
                rate
            )

            if (
                not isfinite(
                    numeric
                )
                or numeric < 0.0
            ):

                raise ValueError(
                    "Event rate must be finite "
                    "and non-negative."
                )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def event_count(
        self,
    ) -> int:

        return len(
            self.observations
        )

    @property
    def has_temporal_span(
        self,
    ) -> bool:

        return (
            self.span_seconds
            >
            0.0
        )

    def event_type_count(
        self,
        event_type: str,
    ) -> int:

        normalized = (
            str(
                event_type
            )
            .strip()
            .lower()
        )

        for (
            type_name,
            count,
        ) in self.event_type_counts:

            if (
                type_name
                ==
                normalized
            ):

                return count

        return 0

    def entity_event_count(
        self,
        entity_id: UUID,
    ) -> int:

        if not isinstance(
            entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        for (
            item_entity_id,
            count,
        ) in self.entity_event_counts:

            if (
                item_entity_id
                ==
                entity_id
            ):

                return count

        return 0


# ==========================================================
# Service
# ==========================================================


class TemporalFeatureExtractionService:
    """
    Pure Phase 4.1 temporal feature extractor.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        events: list[
            TimelineEvent
        ],
        config: (
            TemporalFeatureExtractionConfig
            | None
        ) = None,
    ) -> TemporalFeatureResult:
        """
        Analyze TimelineEvent occurrence timestamps.

        No database writes are performed.
        """

        if not isinstance(
            events,
            list,
        ):

            raise TypeError(
                "events must be a list."
            )

        for event in events:

            if not isinstance(
                event,
                TimelineEvent,
            ):

                raise TypeError(
                    "events must contain "
                    "TimelineEvent objects."
                )

        config = (
            config
            or
            TemporalFeatureExtractionConfig()
        )

        if not isinstance(
            config,
            TemporalFeatureExtractionConfig,
        ):

            raise TypeError(
                "config must be "
                "TemporalFeatureExtractionConfig."
            )

        case_id = (
            self._validate_case_scope(
                events
            )
        )

        (
            observations,
            diagnostics,
        ) = (
            self._normalize_events(
                events,
                config=config,
            )
        )

        return self._extract_features(
            case_id=case_id,
            observations=observations,
            diagnostics=diagnostics,
        )

    # ==========================================================
    # Case scope
    # ==========================================================

    @staticmethod
    def _validate_case_scope(
        events: list[
            TimelineEvent
        ],
    ) -> UUID | None:

        if not events:

            return None

        case_ids: set[
            UUID
        ] = set()

        for event in events:

            if not isinstance(
                event.case_id,
                UUID,
            ):

                raise TypeError(
                    "TimelineEvent.case_id "
                    "must be UUID."
                )

            case_ids.add(
                event.case_id
            )

        if len(
            case_ids
        ) != 1:

            raise ValueError(
                "Temporal feature extraction "
                "cannot mix multiple cases."
            )

        return next(
            iter(
                case_ids
            )
        )

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_events(
        self,
        events: list[
            TimelineEvent
        ],
        *,
        config: TemporalFeatureExtractionConfig,
    ) -> tuple[
        tuple[
            TemporalObservation,
            ...,
        ],
        TemporalNormalizationDiagnostics,
    ]:

        observations: list[
            TemporalObservation
        ] = []

        rejected: list[
            RejectedTemporalTimestamp
        ] = []

        assumed_timezone_count = 0

        for event in events:

            if not isinstance(
                event.id,
                UUID,
            ):

                raise TypeError(
                    "Persisted TimelineEvent.id "
                    "must be UUID."
                )

            raw_timestamp = (
                self._raw_timestamp_text(
                    event.event_time
                )
            )

            try:

                (
                    timestamp,
                    assumed_timezone,
                ) = (
                    self._parse_timestamp(
                        event.event_time,
                        config=config,
                    )
                )

            except ValueError as error:

                rejected_item = (
                    RejectedTemporalTimestamp(
                        event_id=event.id,
                        raw_timestamp=(
                            raw_timestamp
                        ),
                        reason=str(
                            error
                        ),
                    )
                )

                if (
                    config
                    .strict_invalid_timestamps
                ):

                    raise ValueError(
                        "Invalid timeline timestamp "
                        f"for event {event.id}: "
                        f"{error}"
                    ) from error

                rejected.append(
                    rejected_item
                )

                continue

            if assumed_timezone:

                assumed_timezone_count += 1

            event_type = (
                event.event_type.value
                if hasattr(
                    event.event_type,
                    "value",
                )
                else str(
                    event.event_type
                )
            )

            observations.append(
                TemporalObservation(
                    event_id=event.id,
                    case_id=event.case_id,
                    entity_id=event.entity_id,
                    event_type=event_type,
                    timestamp=timestamp,
                    raw_timestamp=(
                        raw_timestamp
                    ),
                )
            )

        observations.sort(
            key=lambda item: (
                item.timestamp,
                str(
                    item.event_id
                ),
            )
        )

        rejected.sort(
            key=lambda item: (
                str(
                    item.event_id
                )
            )
        )

        diagnostics = (
            TemporalNormalizationDiagnostics(
                input_event_count=len(
                    events
                ),
                accepted_event_count=len(
                    observations
                ),
                rejected_event_count=len(
                    rejected
                ),
                assumed_timezone_count=(
                    assumed_timezone_count
                ),
                rejected_timestamps=tuple(
                    rejected
                ),
            )
        )

        return (
            tuple(
                observations
            ),
            diagnostics,
        )

    # ==========================================================
    # Timestamp parser
    # ==========================================================

    @staticmethod
    def _parse_timestamp(
        value: Any,
        *,
        config: TemporalFeatureExtractionConfig,
    ) -> tuple[
        datetime,
        bool,
    ]:
        """
        Parse and normalize occurrence timestamp.

        Returns:

            normalized datetime
            whether a timezone had to be assumed
        """

        if isinstance(
            value,
            datetime,
        ):

            parsed = value

        elif isinstance(
            value,
            str,
        ):

            text = (
                value.strip()
            )

            if not text:

                raise ValueError(
                    "Timestamp is empty."
                )

            # ISO-8601 Z compatibility.
            if text.endswith(
                "Z"
            ):

                text = (
                    text[
                        :-1
                    ]
                    +
                    "+00:00"
                )

            try:

                parsed = (
                    datetime
                    .fromisoformat(
                        text
                    )
                )

            except ValueError as error:

                raise ValueError(
                    "Timestamp is not valid "
                    "ISO-8601."
                ) from error

        else:

            raise ValueError(
                "Timestamp must be an ISO string "
                "or datetime."
            )

        assumed_timezone = False

        if (
            parsed.tzinfo
            is None
            or
            parsed.utcoffset()
            is None
        ):

            if (
                config.naive_timezone
                is None
            ):

                raise ValueError(
                    "Naive timestamp has no "
                    "configured timezone."
                )

            parsed = parsed.replace(
                tzinfo=(
                    config.naive_timezone
                )
            )

            assumed_timezone = True

        normalized = (
            parsed.astimezone(
                config.analysis_timezone
            )
        )

        return (
            normalized,
            assumed_timezone,
        )

    @staticmethod
    def _raw_timestamp_text(
        value: Any,
    ) -> str:

        if isinstance(
            value,
            datetime,
        ):

            return (
                value.isoformat()
            )

        return str(
            value
        )

    # ==========================================================
    # Feature extraction
    # ==========================================================

    def _extract_features(
        self,
        *,
        case_id: UUID | None,
        observations: tuple[
            TemporalObservation,
            ...,
        ],
        diagnostics: (
            TemporalNormalizationDiagnostics
        ),
    ) -> TemporalFeatureResult:

        if not observations:

            return TemporalFeatureResult(
                case_id=case_id,
                observations=(),
                diagnostics=diagnostics,
                first_timestamp=None,
                last_timestamp=None,
                span_seconds=0.0,
                intervals_seconds=(),
                interval_statistics=(
                    TemporalIntervalStatistics(
                        count=0,
                        minimum_seconds=None,
                        maximum_seconds=None,
                        mean_seconds=None,
                        median_seconds=None,
                    )
                ),
                unique_timestamp_count=0,
                simultaneous_event_count=0,
                events_per_hour=None,
                events_per_day=None,
                hour_counts=tuple(
                    0
                    for _
                    in range(
                        24
                    )
                ),
                weekday_counts=tuple(
                    0
                    for _
                    in range(
                        7
                    )
                ),
                event_type_counts=(),
                entity_event_counts=(),
                unassigned_entity_event_count=0,
            )

        first_timestamp = (
            observations[
                0
            ].timestamp
        )

        last_timestamp = (
            observations[
                -1
            ].timestamp
        )

        span_seconds = (
            last_timestamp
            -
            first_timestamp
        ).total_seconds()

        intervals = tuple(
            (
                current.timestamp
                -
                previous.timestamp
            ).total_seconds()
            for previous, current
            in zip(
                observations,
                observations[
                    1:
                ],
            )
        )

        interval_statistics = (
            self._build_interval_statistics(
                intervals
            )
        )

        unique_timestamps = {
            observation.timestamp
            for observation
            in observations
        }

        unique_timestamp_count = len(
            unique_timestamps
        )

        simultaneous_event_count = (
            len(
                observations
            )
            -
            unique_timestamp_count
        )

        if span_seconds > 0.0:

            span_hours = (
                span_seconds
                /
                3600.0
            )

            span_days = (
                span_seconds
                /
                86400.0
            )

            events_per_hour = (
                len(
                    observations
                )
                /
                span_hours
            )

            events_per_day = (
                len(
                    observations
                )
                /
                span_days
            )

        else:

            events_per_hour = None

            events_per_day = None

        hour_counter = [
            0
            for _
            in range(
                24
            )
        ]

        weekday_counter = [
            0
            for _
            in range(
                7
            )
        ]

        type_counter: Counter[
            str
        ] = Counter()

        entity_counter: Counter[
            UUID
        ] = Counter()

        unassigned_entity_event_count = 0

        for observation in observations:

            hour_counter[
                observation
                .timestamp
                .hour
            ] += 1

            weekday_counter[
                observation
                .timestamp
                .weekday()
            ] += 1

            type_counter[
                observation.event_type
            ] += 1

            if (
                observation.entity_id
                is None
            ):

                unassigned_entity_event_count += 1

            else:

                entity_counter[
                    observation.entity_id
                ] += 1

        event_type_counts = tuple(
            sorted(
                type_counter.items(),
                key=lambda item: (
                    item[
                        0
                    ]
                ),
            )
        )

        entity_event_counts = tuple(
            sorted(
                entity_counter.items(),
                key=lambda item: (
                    str(
                        item[
                            0
                        ]
                    )
                ),
            )
        )

        return TemporalFeatureResult(
            case_id=case_id,
            observations=observations,
            diagnostics=diagnostics,
            first_timestamp=(
                first_timestamp
            ),
            last_timestamp=(
                last_timestamp
            ),
            span_seconds=(
                span_seconds
            ),
            intervals_seconds=(
                intervals
            ),
            interval_statistics=(
                interval_statistics
            ),
            unique_timestamp_count=(
                unique_timestamp_count
            ),
            simultaneous_event_count=(
                simultaneous_event_count
            ),
            events_per_hour=(
                events_per_hour
            ),
            events_per_day=(
                events_per_day
            ),
            hour_counts=tuple(
                hour_counter
            ),
            weekday_counts=tuple(
                weekday_counter
            ),
            event_type_counts=(
                event_type_counts
            ),
            entity_event_counts=(
                entity_event_counts
            ),
            unassigned_entity_event_count=(
                unassigned_entity_event_count
            ),
        )

    # ==========================================================
    # Interval statistics
    # ==========================================================

    @staticmethod
    def _build_interval_statistics(
        intervals: tuple[
            float,
            ...,
        ],
    ) -> TemporalIntervalStatistics:

        if not intervals:

            return (
                TemporalIntervalStatistics(
                    count=0,
                    minimum_seconds=None,
                    maximum_seconds=None,
                    mean_seconds=None,
                    median_seconds=None,
                )
            )

        for interval in intervals:

            if (
                not isfinite(
                    interval
                )
                or interval < 0.0
            ):

                raise ValueError(
                    "Chronological intervals "
                    "must be finite and "
                    "non-negative."
                )

        return TemporalIntervalStatistics(
            count=len(
                intervals
            ),
            minimum_seconds=min(
                intervals
            ),
            maximum_seconds=max(
                intervals
            ),
            mean_seconds=mean(
                intervals
            ),
            median_seconds=median(
                intervals
            ),
        )