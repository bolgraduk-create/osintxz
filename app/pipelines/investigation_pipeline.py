"""
Investigation pipeline.

Coordinates the complete investigation flow.

Responsibilities:

- collect evidence
- start evidence processing

The pipeline does not know
how investigation is performed internally.
"""

from __future__ import annotations

from uuid import UUID

from app.services.collection_service import CollectionService
from app.services.evidence_processing_service import (
    EvidenceProcessingService,
)


class InvestigationPipeline:
    """
    High-level investigation orchestrator.
    """

    def __init__(
        self,
        collection_service: CollectionService,
        processing_service: EvidenceProcessingService,
    ) -> None:

        self.collection_service = collection_service

        self.processing_service = processing_service

    def process_collected_items(
        self,
        case_id: UUID,
        items,
    ) -> None:
        """
        Store collected items
        and execute investigation.
        """

        self.collection_service.collect_many(
            case_id=case_id,
            items=items,
        )

        self.processing_service.process_case(
            case_id,
        )

    def process_existing_case(
        self,
        case_id: UUID,
    ) -> None:
        """
        Execute investigation
        for existing evidence.
        """

        self.processing_service.process_case(
            case_id,
        )