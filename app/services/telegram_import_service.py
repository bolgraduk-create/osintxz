from __future__ import annotations

"""
Telegram import service.

Imports Telegram export into investigation.
"""

from pathlib import Path
from uuid import UUID

from app.collectors.telegram.telegram_collector import (
    TelegramCollector,
)

from app.services.collection_service import (
    CollectionService,
)

from app.services.evidence_processing_service import (
    EvidenceProcessingService,
)

from app.services.source_service import (
    SourceService,
)


class TelegramImportService:
    """
    High-level Telegram import workflow.
    """

    def __init__(
        self,
        collector: TelegramCollector,
        collection_service: CollectionService,
        processing_service: EvidenceProcessingService,
        source_service: SourceService,
    ) -> None:

        self.collector = collector

        self.collection_service = collection_service

        self.processing_service = processing_service

        self.source_service = source_service

    def import_export(
        self,
        case_id: UUID,
        path: str | Path,
    ) -> None:
        """
        Import Telegram export.
        """

        items = self.collector.collect(
            path
        )

        source = self.source_service.create_source(
            case_id=case_id,
            source_type="telegram",
            title="Telegram Export",
        )

        self.collection_service.collect_many(
            case_id=case_id,
            source_id=source.id,
            items=items,
        )

        self.processing_service.process_case(
            case_id
        )