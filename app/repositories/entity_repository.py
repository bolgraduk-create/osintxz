"""
Entity repository.

Provides database operations
for extracted entities.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entity import (
    Entity,
    EntityType,
)
from app.repositories.base_repository import (
    BaseRepository,
)


class EntityRepository(
    BaseRepository[Entity],
):
    """
    Repository for Entity model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Entity,
        )

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Entity]:
        """
        Return entities belonging to a case.
        """

        result = self.session.execute(
            select(Entity)
            .where(
                Entity.case_id == case_id,
            )
            .order_by(Entity.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_type(
        self,
        entity_type: EntityType,
    ) -> list[Entity]:
        """
        Return entities by type.
        """

        result = self.session.execute(
            select(Entity)
            .where(
                Entity.entity_type == entity_type,
            )
            .order_by(Entity.created_at)
        )

        return list(
            result.scalars().all()
        )

    def find_by_value(
        self,
        value: str,
    ) -> list[Entity]:
        """
        Find entities by exact value.
        """

        result = self.session.execute(
            select(Entity)
            .where(
                Entity.value == value,
            )
            .order_by(Entity.created_at)
        )

        return list(
            result.scalars().all()
        )

    def find_by_normalized_value(
        self,
        normalized_value: str,
    ) -> list[Entity]:
        """
        Find entities by normalized value.
        """

        result = self.session.execute(
            select(Entity)
            .where(
                Entity.normalized_value == normalized_value,
            )
            .order_by(Entity.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_case_entities_by_type(
        self,
        case_id: UUID,
        entity_type: EntityType,
    ) -> list[Entity]:
        """
        Return entities of a specific type
        inside a case.
        """

        result = self.session.execute(
            select(Entity)
            .where(
                Entity.case_id == case_id,
                Entity.entity_type == entity_type,
            )
            .order_by(Entity.created_at)
        )

        return list(
            result.scalars().all()
        )