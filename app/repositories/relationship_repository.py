"""
Relationship repository.

Provides database operations
for entity relationships.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.relationship import (
    Relationship,
    RelationshipType,
)
from app.repositories.base_repository import (
    BaseRepository,
)


class RelationshipRepository(
    BaseRepository[Relationship],
):
    """
    Repository for Relationship model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Relationship,
        )

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Relationship]:
        """
        Return relationships inside a case.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                Relationship.case_id == case_id,
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_source_entity(
        self,
        entity_id: UUID,
    ) -> list[Relationship]:
        """
        Return relationships where the entity
        is the source.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                Relationship.source_entity_id == entity_id,
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_target_entity(
        self,
        entity_id: UUID,
    ) -> list[Relationship]:
        """
        Return relationships where the entity
        is the target.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                Relationship.target_entity_id == entity_id,
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_between_entities(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> list[Relationship]:
        """
        Return relationships between
        two entities.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                Relationship.source_entity_id == source_entity_id,
                Relationship.target_entity_id == target_entity_id,
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_type(
        self,
        relationship_type: RelationshipType,
    ) -> list[Relationship]:
        """
        Return relationships of a given type.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                Relationship.relationship_type == relationship_type,
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_entity_connections(
        self,
        entity_id: UUID,
    ) -> list[Relationship]:
        """
        Return every relationship
        involving an entity.
        """

        result = self.session.execute(
            select(Relationship)
            .where(
                (Relationship.source_entity_id == entity_id)
                | (Relationship.target_entity_id == entity_id)
            )
            .order_by(Relationship.created_at)
        )

        return list(
            result.scalars().all()
        )