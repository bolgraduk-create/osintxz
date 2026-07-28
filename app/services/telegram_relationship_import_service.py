"""
Telegram relationship import service.

Imports Telegram participant interactions
into investigation relationships.

Responsibilities:

- convert Telegram interactions
- create investigation relationships
- normalize relationship strength

Does NOT:

- parse Telegram exports
- perform AI analysis
- create entities
"""

from __future__ import annotations

from uuid import UUID

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.telegram_interaction_service import (
    TelegramInteractionService,
)


class TelegramRelationshipImportService:
    """
    Imports Telegram interactions into investigation.
    """

    def __init__(
        self,
        relationship_service: RelationshipService,
        interaction_service: TelegramInteractionService,
    ):

        self.relationship_service = relationship_service

        self.interaction_service = interaction_service

    def import_relationships(
        self,
        case_id: UUID,
        conversations,
    ) -> None:
        """
        Import Telegram participant relationships.
        """

        relationships = (
            self.interaction_service.interaction_matrix(
                conversations
            )
        )

        for (
            participants,
            strength,
        ) in relationships.items():

            source, target = participants

            self.relationship_service.create(
                case_id=case_id,
                source_value=source,
                target_value=target,
                relationship_type="telegram_interaction",
                strength=float(strength),
                metadata={
                    "source": "telegram",
                },
            )