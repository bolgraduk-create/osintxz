"""
Unified temporal analysis.

Combines the completed Phase 4 temporal-analysis
components into one deterministic analytical pipeline.

Pipeline:

TimelineEvent[]
    ↓
TemporalFeatureExtractionService
    ↓
TemporalFeatureResult
    ↓
TemporalCorrelationService
    ↓
TemporalCorrelationResult
    ├───────────────────────────────┐
    ↓                               ↓
TemporalBurstDetectionService       TemporalChangePointDetectionService
    ↓                               ↓
TemporalBurstDetectionResult        TemporalChangePointDetectionResult
    └───────────────┬───────────────┘
                    ↓
        UnifiedTemporalAnalysisResult

Important semantic boundaries:

Temporal features
    != evidence

Temporal correlation
    != causation

Temporal burst
    != anomaly proof

Temporal change point
    != coordination proof

No result produced here automatically becomes:

- Evidence
- Relationship
- Entity Resolution signal
- identity conclusion
- persisted investigation fact

Does NOT:

- query the database
- write to the database
- modify TimelineEvent
- use created_at as occurrence time
- create Evidence
- create Relationship
- merge Entities
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from uuid import UUID

from app.analysis.temporal_burst_detection import (
    TemporalBurstDetectionConfig,
    TemporalBurstDetectionResult,
    TemporalBurstDetectionService,
)

from app.analysis.temporal_change_point_detection import (
    TemporalChangePointDetectionConfig,
    TemporalChangePointDetectionResult,
    TemporalChangePointDetectionService,
)

from app.analysis.temporal_correlation import (
    TemporalCorrelationConfig,
    TemporalCorrelationResult,
    TemporalCorrelationService,
)

from app.analysis.temporal_feature_extraction import (
    TemporalFeatureExtractionConfig,
    TemporalFeatureExtractionService,
    TemporalFeatureResult,
)

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
class UnifiedTemporalAnalysisConfig:
    """
    Configuration for the complete temporal pipeline.

    Each analytical component retains its own explicit
    configuration and semantics.
    """

    feature_extraction: (
        TemporalFeatureExtractionConfig
    ) = field(
        default_factory=(
            TemporalFeatureExtractionConfig
        )
    )

    correlation: TemporalCorrelationConfig = field(
        default_factory=(
            TemporalCorrelationConfig
        )
    )

    burst_detection: (
        TemporalBurstDetectionConfig
    ) = field(
        default_factory=(
            TemporalBurstDetectionConfig
        )
    )

    change_point_detection: (
        TemporalChangePointDetectionConfig
    ) = field(
        default_factory=(
            TemporalChangePointDetectionConfig
        )
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.feature_extraction,
            TemporalFeatureExtractionConfig,
        ):

            raise TypeError(
                "feature_extraction must be "
                "TemporalFeatureExtractionConfig."
            )

        if not isinstance(
            self.correlation,
            TemporalCorrelationConfig,
        ):

            raise TypeError(
                "correlation must be "
                "TemporalCorrelationConfig."
            )

        if not isinstance(
            self.burst_detection,
            TemporalBurstDetectionConfig,
        ):

            raise TypeError(
                "burst_detection must be "
                "TemporalBurstDetectionConfig."
            )

        if not isinstance(
            self.change_point_detection,
            TemporalChangePointDetectionConfig,
        ):

            raise TypeError(
                "change_point_detection must be "
                "TemporalChangePointDetectionConfig."
            )


# ==========================================================
# Statistics
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedTemporalStatistics:
    """
    Cross-module temporal statistics.

    Counts remain independent analytical facts.
    No combined intelligence score is created.
    """

    input_event_count: int

    accepted_event_count: int

    rejected_event_count: int

    window_count: int

    entity_series_count: int

    event_type_series_count: int

    entity_correlation_count: int

    event_type_correlation_count: int

    burst_count: int

    burst_episode_count: int

    change_point_count: int

    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "input_event_count",
            "accepted_event_count",
            "rejected_event_count",
            "window_count",
            "entity_series_count",
            "event_type_series_count",
            "entity_correlation_count",
            "event_type_correlation_count",
            "burst_count",
            "burst_episode_count",
            "change_point_count",
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
                or
                value < 0
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
                "Accepted + rejected events must "
                "equal input events."
            )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UnifiedTemporalAnalysisResult:
    """
    Complete result of Phase 4 Temporal Analytics.

    Every underlying module result remains independently
    accessible and retains its own mathematical meaning.
    """

    case_id: (
        UUID
        | None
    )

    config: UnifiedTemporalAnalysisConfig

    features: TemporalFeatureResult

    correlation: TemporalCorrelationResult

    bursts: TemporalBurstDetectionResult

    change_points: (
        TemporalChangePointDetectionResult
    )

    statistics: UnifiedTemporalStatistics

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
            self.config,
            UnifiedTemporalAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "UnifiedTemporalAnalysisConfig."
            )

        if not isinstance(
            self.features,
            TemporalFeatureResult,
        ):

            raise TypeError(
                "features must be "
                "TemporalFeatureResult."
            )

        if not isinstance(
            self.correlation,
            TemporalCorrelationResult,
        ):

            raise TypeError(
                "correlation must be "
                "TemporalCorrelationResult."
            )

        if not isinstance(
            self.bursts,
            TemporalBurstDetectionResult,
        ):

            raise TypeError(
                "bursts must be "
                "TemporalBurstDetectionResult."
            )

        if not isinstance(
            self.change_points,
            TemporalChangePointDetectionResult,
        ):

            raise TypeError(
                "change_points must be "
                "TemporalChangePointDetectionResult."
            )

        if not isinstance(
            self.statistics,
            UnifiedTemporalStatistics,
        ):

            raise TypeError(
                "statistics must be "
                "UnifiedTemporalStatistics."
            )

        self._validate_case_scope()

        self._validate_windows()

        self._validate_statistics()

    # ==========================================================
    # Case consistency
    # ==========================================================

    def _validate_case_scope(
        self,
    ) -> None:

        module_case_ids = (
            self.features.case_id,
            self.correlation.case_id,
            self.bursts.case_id,
            self.change_points.case_id,
        )

        if any(
            case_id
            !=
            self.case_id
            for case_id
            in module_case_ids
        ):

            raise ValueError(
                "Temporal module case IDs "
                "are inconsistent."
            )

    # ==========================================================
    # Window consistency
    # ==========================================================

    def _validate_windows(
        self,
    ) -> None:

        expected_starts = (
            self.correlation
            .window_starts_utc
        )

        expected_seconds = (
            self.correlation
            .window_seconds
        )

        if (
            self.bursts.window_starts_utc
            !=
            expected_starts
        ):

            raise ValueError(
                "Burst-analysis windows do not "
                "match correlation windows."
            )

        if (
            self.change_points
            .window_starts_utc
            !=
            expected_starts
        ):

            raise ValueError(
                "Change-point windows do not "
                "match correlation windows."
            )

        if (
            self.bursts.window_seconds
            !=
            expected_seconds
        ):

            raise ValueError(
                "Burst window width does not "
                "match correlation."
            )

        if (
            self.change_points
            .window_seconds
            !=
            expected_seconds
        ):

            raise ValueError(
                "Change-point window width does "
                "not match correlation."
            )

    # ==========================================================
    # Statistics consistency
    # ==========================================================

    def _validate_statistics(
        self,
    ) -> None:

        expected = (
            UnifiedTemporalStatistics(
                input_event_count=(
                    self.features
                    .diagnostics
                    .input_event_count
                ),
                accepted_event_count=(
                    self.features
                    .diagnostics
                    .accepted_event_count
                ),
                rejected_event_count=(
                    self.features
                    .diagnostics
                    .rejected_event_count
                ),
                window_count=(
                    self.correlation
                    .window_count
                ),
                entity_series_count=(
                    self.correlation
                    .entity_series_count
                ),
                event_type_series_count=(
                    self.correlation
                    .event_type_series_count
                ),
                entity_correlation_count=len(
                    self.correlation
                    .entity_correlations
                ),
                event_type_correlation_count=len(
                    self.correlation
                    .event_type_correlations
                ),
                burst_count=(
                    self.bursts
                    .burst_count
                ),
                burst_episode_count=(
                    self.bursts
                    .episode_count
                ),
                change_point_count=(
                    self.change_points
                    .change_point_count
                ),
            )
        )

        if (
            self.statistics
            !=
            expected
        ):

            raise ValueError(
                "Unified temporal statistics "
                "are inconsistent."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def event_count(
        self,
    ) -> int:

        return (
            self.statistics
            .accepted_event_count
        )

    @property
    def window_count(
        self,
    ) -> int:

        return (
            self.statistics
            .window_count
        )

    @property
    def burst_count(
        self,
    ) -> int:

        return (
            self.statistics
            .burst_count
        )

    @property
    def change_point_count(
        self,
    ) -> int:

        return (
            self.statistics
            .change_point_count
        )

    @property
    def has_rejected_timestamps(
        self,
    ) -> bool:

        return (
            self.statistics
            .rejected_event_count
            >
            0
        )


# ==========================================================
# Service
# ==========================================================


class UnifiedTemporalAnalysisService:
    """
    Executes the complete Phase 4 temporal pipeline.

    Each analysis stage is injected independently so the
    service remains testable and preserves module
    boundaries.
    """

    def __init__(
        self,
        feature_extraction_service: (
            TemporalFeatureExtractionService
            | None
        ) = None,
        correlation_service: (
            TemporalCorrelationService
            | None
        ) = None,
        burst_detection_service: (
            TemporalBurstDetectionService
            | None
        ) = None,
        change_point_detection_service: (
            TemporalChangePointDetectionService
            | None
        ) = None,
    ) -> None:

        if (
            feature_extraction_service
            is not None
            and
            not isinstance(
                feature_extraction_service,
                TemporalFeatureExtractionService,
            )
        ):

            raise TypeError(
                "feature_extraction_service must be "
                "TemporalFeatureExtractionService."
            )

        if (
            correlation_service
            is not None
            and
            not isinstance(
                correlation_service,
                TemporalCorrelationService,
            )
        ):

            raise TypeError(
                "correlation_service must be "
                "TemporalCorrelationService."
            )

        if (
            burst_detection_service
            is not None
            and
            not isinstance(
                burst_detection_service,
                TemporalBurstDetectionService,
            )
        ):

            raise TypeError(
                "burst_detection_service must be "
                "TemporalBurstDetectionService."
            )

        if (
            change_point_detection_service
            is not None
            and
            not isinstance(
                change_point_detection_service,
                TemporalChangePointDetectionService,
            )
        ):

            raise TypeError(
                "change_point_detection_service must be "
                "TemporalChangePointDetectionService."
            )

        self.feature_extraction_service = (
            feature_extraction_service
            or
            TemporalFeatureExtractionService()
        )

        self.correlation_service = (
            correlation_service
            or
            TemporalCorrelationService()
        )

        self.burst_detection_service = (
            burst_detection_service
            or
            TemporalBurstDetectionService()
        )

        self.change_point_detection_service = (
            change_point_detection_service
            or
            TemporalChangePointDetectionService()
        )

    # ==========================================================
    # Complete temporal analysis
    # ==========================================================

    def analyze(
        self,
        events: list[
            TimelineEvent
        ],
        config: (
            UnifiedTemporalAnalysisConfig
            | None
        ) = None,
    ) -> UnifiedTemporalAnalysisResult:
        """
        Execute Phase 4 exactly once per module.

        No database persistence is performed.
        """

        if not isinstance(
            events,
            list,
        ):

            raise TypeError(
                "events must be a list."
            )

        config = (
            config
            or
            UnifiedTemporalAnalysisConfig()
        )

        if not isinstance(
            config,
            UnifiedTemporalAnalysisConfig,
        ):

            raise TypeError(
                "config must be "
                "UnifiedTemporalAnalysisConfig."
            )

        # ======================================================
        # 4.1
        # ======================================================

        features = (
            self.feature_extraction_service
            .analyze(
                events,
                config.feature_extraction,
            )
        )

        # ======================================================
        # 4.2
        # ======================================================

        correlation = (
            self.correlation_service
            .analyze(
                features,
                config.correlation,
            )
        )

        # ======================================================
        # 4.3
        # ======================================================

        bursts = (
            self.burst_detection_service
            .analyze(
                correlation,
                config.burst_detection,
            )
        )

        # ======================================================
        # 4.4
        # ======================================================

        change_points = (
            self.change_point_detection_service
            .analyze(
                correlation,
                config.change_point_detection,
            )
        )

        # ======================================================
        # Unified statistics
        # ======================================================

        statistics = (
            UnifiedTemporalStatistics(
                input_event_count=(
                    features
                    .diagnostics
                    .input_event_count
                ),
                accepted_event_count=(
                    features
                    .diagnostics
                    .accepted_event_count
                ),
                rejected_event_count=(
                    features
                    .diagnostics
                    .rejected_event_count
                ),
                window_count=(
                    correlation.window_count
                ),
                entity_series_count=(
                    correlation
                    .entity_series_count
                ),
                event_type_series_count=(
                    correlation
                    .event_type_series_count
                ),
                entity_correlation_count=len(
                    correlation
                    .entity_correlations
                ),
                event_type_correlation_count=len(
                    correlation
                    .event_type_correlations
                ),
                burst_count=(
                    bursts.burst_count
                ),
                burst_episode_count=(
                    bursts.episode_count
                ),
                change_point_count=(
                    change_points
                    .change_point_count
                ),
            )
        )

        return (
            UnifiedTemporalAnalysisResult(
                case_id=(
                    features.case_id
                ),
                config=config,
                features=features,
                correlation=correlation,
                bursts=bursts,
                change_points=(
                    change_points
                ),
                statistics=statistics,
            )
        )