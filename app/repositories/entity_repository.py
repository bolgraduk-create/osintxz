"""
Entity repository.

Provides database operations
for extracted entities.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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

    def get_page(self, *, limit: int = 100, offset: int = 0, case_id: UUID | None = None) -> list[Entity]:
        statement = (
            select(Entity)
            .where(Entity.deleted_at.is_(None))
            .order_by(Entity.created_at, Entity.id)
            .offset(max(0, int(offset)))
            .limit(max(1, min(int(limit), 500)))
        )
        if case_id is not None:
            statement = statement.where(Entity.case_id == case_id)
        return list(self.session.scalars(statement).all())

    def count_all(self, *, case_id: UUID | None = None) -> int:
        statement = select(func.count(Entity.id))
        statement = statement.where(Entity.deleted_at.is_(None))
        if case_id is not None:
            statement = statement.where(Entity.case_id == case_id)
        return int(self.session.scalar(statement) or 0)

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

    def find_in_case(
        self,
        case_id: UUID,
        entity_type: EntityType,
        normalized_value: str,
    ) -> Entity | None:
        """
        Find one entity inside a case by type and normalized value.
        """

        result = self.session.execute(
            select(
                Entity
            )
            .where(
                Entity.case_id == case_id,
                Entity.entity_type == entity_type,
                Entity.normalized_value == normalized_value,
                Entity.deleted_at.is_(None),
            )
            .limit(
                1
            )
        )

        return result.scalar_one_or_none()

    def search_case_structured(
        self,
        case_id: UUID,
        *,
        entity_types: tuple[EntityType, ...] = (),
        object_ids: tuple[UUID, ...] = (),
        values: tuple[str, ...] = (),
        normalized_values: tuple[str, ...] = (),
        include_deleted: bool = False,
        limit: int = 200,
    ) -> list[Entity]:
        """Return Entity rows matching explicit structured filters."""

        statement = select(Entity).where(Entity.case_id == case_id)

        if not include_deleted:
            statement = statement.where(Entity.deleted_at.is_(None))

        if entity_types:
            statement = statement.where(Entity.entity_type.in_(entity_types))

        if object_ids:
            statement = statement.where(Entity.id.in_(object_ids))

        if values:
            statement = statement.where(Entity.value.in_(values))

        if normalized_values:
            statement = statement.where(
                Entity.normalized_value.in_(normalized_values)
            )

        statement = statement.order_by(
            Entity.created_at.desc(),
            Entity.id,
        ).limit(max(1, int(limit)))

        result = self.session.execute(statement)
        return list(result.scalars().all())
