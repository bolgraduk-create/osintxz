"""
Evidence processing service.

Coordinates investigation processing
starting from stored Evidence.

Responsibilities:

- process investigation evidence
- orchestrate investigation services
- execute processing pipeline

Does NOT:

- collect evidence
- communicate with collectors
- implement business logic
"""

from __future__ import annotations

from uuid import UUID

from app.services.entity_service import EntityService
from app.services.relationship_service import RelationshipService
from app.services.timeline_service import TimelineService
from app.services.report_service import ReportService
from app.services.ai_investigation_service import (
    AIInvestigationService,
)


class EvidenceProcessingService:
    """
    Executes investigation processing
    starting from stored evidence.
    """

    def __init__(
        self,
        entity_service: EntityService,
        relationship_service: RelationshipService,
        timeline_service: TimelineService,
        report_service: ReportService,
        ai_service: AIInvestigationService,
    ) -> None:

        self.entity_service = entity_service

        self.relationship_service = relationship_service

        self.timeline_service = timeline_service

        self.report_service = report_service

        self.ai_service = ai_service

    def process_case(
        self,
        case_id: UUID,
    ) -> None:
        """
        Execute complete investigation processing.
        """

        self.entity_service.process_case(
            case_id
        )

        self.relationship_service.process_case(
            case_id
        )

        self.timeline_service.process_case(
            case_id
        )

        self.report_service.process_case(
            case_id
        )

        self.ai_service.analyze(
            case_id
        )