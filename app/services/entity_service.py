"""
Entity service.

Contains business logic related
to extracted entities.

Examples:

- Person
- Organization
- Phone
- Email
- Username
- Domain
- IP
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entity import (
    Entity,
    EntityType,
)

from app.repositories.entity_repository import (
    EntityRepository,
)


class EntityService:
    """
    Service for managing entities.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = EntityRepository(
            session
        )

    def create_entity(
        self,
        case_id: UUID,
        entity_type: EntityType,
        value: str,
        normalized_value: str | None = None,
        confidence: float = 1.0,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Entity:
        """
        Create new entity.
        """

        entity = Entity(
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            normalized_value=normalized_value,
            confidence=confidence,
            metadata_json=metadata_json,
            description=description,
        )

        return self.repository.create(
            entity
        )

    def get_entity(
        self,
        entity_id: UUID,
    ) -> Entity | None:
        """
        Get entity by id.
        """

        return self.repository.get(
            entity_id
        )

    def get_case_entities(
        self,
        case_id: UUID,
    ) -> list[Entity]:
        """
        Return all entities
        belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )

    def find_by_value(
        self,
        value: str,
    ) -> list[Entity]:
        """
        Search entities by value.
        """

        return self.repository.find_by_value(
            value
        )

    def update_confidence(
        self,
        entity_id: UUID,
        confidence: float,
    ) -> Entity | None:
        """
        Update entity confidence score.
        """

        entity = self.repository.get(
            entity_id
        )

        if entity is None:
            return None

        entity.confidence = confidence

        self.repository.session.flush()

        return entity

    def delete_entity(
        self,
        entity_id: UUID,
    ) -> bool:
        """
        Soft delete entity.
        """

        entity = self.repository.get(
            entity_id
        )

        if entity is None:
            return False

        entity.soft_delete()

        self.repository.session.flush()

        return True