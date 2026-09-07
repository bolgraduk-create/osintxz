"""
Investigation temporal-analysis application service.

Connects the investigation timeline persistence layer
to the completed Phase 4 Temporal Analytics pipeline.

Pipeline:

case_id
    ↓
TimelineService
    ↓
TimelineEvent[]
    ↓
UnifiedTemporalAnalysisService
    ↓
UnifiedTemporalAnalysisResult
    ↓
InvestigationTemporalAnalysisResult

Responsibilities:

- provide one application-level temporal-analysis entry point
- load the canonical case timeline
- execute the complete Phase 4 pipeline
- preserve the requested investigation case scope
- keep temporal mathematics separate from persistence

Does NOT:

- create TimelineEvent records
- modify TimelineEvent records
- create Evidence
- create Relationships
- merge Entities
- create Entity Resolution signals
- persist temporal-analysis results
- convert correlation into causation
- convert bursts into facts
- convert change points into evidence
"""

from __future__ import annotations

from dataclasses import dataclass

from uuid import UUID

from app.analysis.unified_temporal_analysis import (
    UnifiedTemporalAnalysisConfig,
    UnifiedTemporalAnalysisResult,
    UnifiedTemporalAnalysisService,
)

from app.services.timeline_service import (
    TimelineService,
)


# ==========================================================
# Application result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationTemporalAnalysisResult:
    """
    Complete temporal-analysis result for one
    investigation case.

    case_id:

        Explicit application-level case scope.

    analysis:

        Complete Phase 4 mathematical result.

    An empty timeline has:

        analysis.case_id == None

    because no TimelineEvent exists from which the
    analysis layer could infer a case.

    The application result still preserves the requested
    investigation case_id.
    """

    case_id: UUID

    analysis: UnifiedTemporalAnalysisResult

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.analysis,
            UnifiedTemporalAnalysisResult,
        ):

            raise TypeError(
                "analysis must be "
                "UnifiedTemporalAnalysisResult."
            )

        if (
            self.analysis.case_id
            is not None
            and
            self.analysis.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Temporal analysis belongs "
                "to another case."
            )

        if (
            self.analysis.case_id
            is None
            and
            self.analysis.event_count
            >
            0
        ):

            raise ValueError(
                "Non-empty temporal analysis "
                "must have a case ID."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def event_count(
        self,
    ) -> int:

        return (
            self.analysis
            .event_count
        )

    @property
    def window_count(
        self,
    ) -> int:

        return (
            self.analysis
            .window_count
        )

    @property
    def burst_count(
        self,
    ) -> int:

        return (
            self.analysis
            .burst_count
        )

    @property
    def change_point_count(
        self,
    ) -> int:

        return (
            self.analysis
            .change_point_count
        )

    @property
    def rejected_timestamp_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .rejected_event_count
        )


# ==========================================================
# Application service
# ==========================================================


class InvestigationTemporalAnalysisService:
    """
    Application orchestration for Phase 4.

    TimelineService owns timeline retrieval.

    UnifiedTemporalAnalysisService owns temporal
    mathematics.

    This service coordinates those two boundaries.
    """

    def __init__(
        self,
        timeline_service: TimelineService,
        unified_temporal_analysis_service: (
            UnifiedTemporalAnalysisService
            | None
        ) = None,
    ) -> None:

        if not isinstance(
            timeline_service,
            TimelineService,
        ):

            raise TypeError(
                "timeline_service must be "
                "TimelineService."
            )

        if (
            unified_temporal_analysis_service
            is not None
            and
            not isinstance(
                unified_temporal_analysis_service,
                UnifiedTemporalAnalysisService,
            )
        ):

            raise TypeError(
                "unified_temporal_analysis_service "
                "must be "
                "UnifiedTemporalAnalysisService."
            )

        self.timeline_service = (
            timeline_service
        )

        self.unified_temporal_analysis_service = (
            unified_temporal_analysis_service
            or
            UnifiedTemporalAnalysisService()
        )

    # ==========================================================
    # Complete case temporal analysis
    # ==========================================================

    def analyze_case(
        self,
        case_id: str | UUID,
        config: (
            UnifiedTemporalAnalysisConfig
            | None
        ) = None,
    ) -> InvestigationTemporalAnalysisResult:
        """
        Execute the complete Phase 4 pipeline for one
        investigation case.

        Database interaction is limited to the existing
        TimelineService read path.

        No analysis persistence is performed.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        events = (
            self.timeline_service
            .get_case_timeline(
                case_uuid
            )
        )

        analysis = (
            self.unified_temporal_analysis_service
            .analyze(
                events,
                config,
            )
        )

        return (
            InvestigationTemporalAnalysisResult(
                case_id=case_uuid,
                analysis=analysis,
            )
        )

    # ==========================================================
    # Case identifier
    # ==========================================================

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:

        if isinstance(
            case_id,
            UUID,
        ):

            return case_id

        try:

            return UUID(
                str(
                    case_id
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                "Invalid investigation case ID."
            ) from error