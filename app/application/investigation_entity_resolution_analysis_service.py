"""
Read-only case-level Entity Resolution analysis.

This application service connects the existing Entity Resolution
mathematical pipeline to one investigation case without performing
entity merges or other persistence operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


from app.entity_resolution.batch_resolution import (
    EntityResolutionBatchResult,
)
from app.services.entity_resolution_pipeline import (
    EntityResolutionPipeline,
)
from app.services.entity_service import (
    EntityService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityResolutionAnalysisResult:
    """
    Read-only Entity Resolution result for one investigation case.
    """

    case_id: UUID

    entities: tuple[
        object,
        ...,
    ]

    resolution: EntityResolutionBatchResult

    def entity_count(
        self,
    ) -> int:
        return len(
            self.entities
        )

    def processed_count(
        self,
    ) -> int:
        return (
            self.resolution
            .processed_count()
        )

    def has_matches(
        self,
    ) -> bool:
        return (
            self.resolution
            .has_matches()
        )

    def has_reviews(
        self,
    ) -> bool:
        return (
            self.resolution
            .has_reviews()
        )


class InvestigationEntityResolutionAnalysisService:
    """
    Execute case-level Entity Resolution without mutation.

    Important:
    - reads existing case Entities
    - generates conservative candidate pairs
    - evaluates identity evidence/signals
    - never calls EntityResolutionPipeline.merge_pair()
    - never writes EntityMerge records
    """

    def __init__(
        self,
        *,
        entity_service: EntityService,
        entity_resolution_pipeline: (
            EntityResolutionPipeline
        ),
    ) -> None:

        self.entity_service = (
            entity_service
        )

        self.entity_resolution_pipeline = (
            entity_resolution_pipeline
        )

    def analyze_case(
        self,
        case_id: str | UUID,
    ) -> InvestigationEntityResolutionAnalysisResult:
        """
        Analyze existing Entities belonging to one case.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        entities = tuple(
            self.entity_service
            .get_case_entities(
                case_uuid
            )
        )

        resolution = (
            self.entity_resolution_pipeline
            .process_entities(
                entities
            )
        )

        if not isinstance(
            resolution,
            EntityResolutionBatchResult,
        ):

            raise TypeError(
                "Entity Resolution pipeline returned "
                "unexpected result type."
            )

        return (
            InvestigationEntityResolutionAnalysisResult(
                case_id=case_uuid,
                entities=entities,
                resolution=resolution,
            )
        )

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:

        if isinstance(
            case_id,
            UUID,
        ):
            return case_id

        normalized = str(
            case_id
            or ""
        ).strip()

        if not normalized:
            raise ValueError(
                "case_id cannot be empty."
            )

        try:
            return UUID(
                normalized
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:

            raise ValueError(
                "case_id must contain a valid UUID."
            ) from exc


__all__ = [
    "InvestigationEntityResolutionAnalysisResult",
    "InvestigationEntityResolutionAnalysisService",
]
