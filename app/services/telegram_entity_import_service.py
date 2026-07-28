"""
Telegram entity import service.

Imports Telegram entities into investigation.

Responsibilities:

- convert Telegram entities
- send entities to EntityService
- prevent duplicate import

Does NOT:

- parse Telegram
- perform AI analysis
- create relationships
"""

from __future__ import annotations

from uuid import UUID

from app.services.entity_service import EntityService
from app.services.telegram_entity_mapper_service import (
    TelegramEntityMapperService,
)


class TelegramEntityImportService:
    """
    Imports Telegram entities into investigation.
    """

    def __init__(
        self,
        entity_service: EntityService,
        mapper: TelegramEntityMapperService,
    ):

        self.entity_service = entity_service
        self.mapper = mapper

    def import_entities(
        self,
        case_id: UUID,
        messages,
    ) -> None:
        """
        Import Telegram participants as investigation entities.
        """

        entities = self.mapper.participants_to_entities(
            messages
        )

        for entity in entities:

            self.entity_service.create(
                case_id=case_id,
                entity_type=entity["type"],
                value=entity["value"],
                metadata=entity["metadata"],
            )