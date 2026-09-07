"""
Evidence processing service.

Coordinates investigation processing
starting from stored evidence.

Responsibilities:

- coordinate processing pipeline
- orchestrate investigation services
- provide single processing entry point

Does NOT:

- collect evidence
- execute AI directly
- implement extraction logic
- access repositories
"""

from __future__ import annotations

from uuid import UUID

from app.services.entity_service import EntityService
from app.services.unified_extraction_service import (
    UnifiedExtractionService,
)
from app.services.relationship_service import RelationshipService
from app.services.timeline_service import TimelineService
from app.services.report_service import ReportService
from app.application.investigation_ai_service import (
    InvestigationAIService,
)


class EvidenceProcessingService:
    """
    Coordinates complete investigation processing.
    """

    def __init__(
        self,
        entity_service: EntityService,
        extraction_service: UnifiedExtractionService,
        relationship_service: RelationshipService,
        timeline_service: TimelineService,
        report_service: ReportService,
        ai_service: InvestigationAIService,
    ) -> None:

        self.entity_service = entity_service

        self.extraction_service = extraction_service

        self.relationship_service = relationship_service

        self.timeline_service = timeline_service

        self.report_service = report_service

        self.ai_service = ai_service

    # ==========================================================
    # Main pipeline
    # ==========================================================

    def process_case(
        self,
        case_id: UUID,
    ) -> None:
        """
        Execute complete investigation processing.
        """

        self.process_entities(case_id)

        self.process_relationships(case_id)

        self.process_timeline(case_id)

        self.process_reports(case_id)

        self.process_ai(case_id)

    # ==========================================================
    # Processing stages
    # ==========================================================

    def process_entities(
        self,
        case_id: UUID,
    ) -> dict:
        """
        Run the shared extraction layer for stored case messages.

        Source-specific importers may call UnifiedExtractionService
        directly with a source_id to avoid reprocessing older sources.
        """

        return self.extraction_service.extract_case_messages(
            case_id=case_id,
        )

    def process_relationships(
        self,
        case_id: UUID,
    ) -> None:
        """
        Relationship extraction stage.
        """

        # TODO
        pass

    def process_timeline(
        self,
        case_id: UUID,
    ) -> None:
        """
        Timeline generation stage.
        """

        # TODO
        pass

    def process_reports(
        self,
        case_id: UUID,
    ) -> None:
        """
        Report generation stage.
        """

        # TODO
        pass

    def process_ai(
        self,
        case_id: UUID,
    ) -> None:
        """
        AI investigation stage.
        """

        if self.ai_service.can_analyze(case_id):

            # TODO
            pass