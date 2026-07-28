"""
Entity merge repository.

Provides database operations
for merge history.
"""

from __future__ import annotations


from uuid import UUID


from sqlalchemy import select
from sqlalchemy.orm import Session


from app.models.entity_merge import (
    EntityMerge,
)


from app.repositories.base_repository import (
    BaseRepository,
)



class EntityMergeRepository(
    BaseRepository[EntityMerge],
):
    """
    Repository for EntityMerge model.
    """


    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            EntityMerge,
        )



    def get_by_source_entity(
        self,
        entity_id: UUID,
    ) -> list[EntityMerge]:
        """
        Return merges where entity
        was source.
        """

        result = self.session.execute(
            select(EntityMerge)
            .where(
                EntityMerge.source_entity_id
                ==
                entity_id
            )
        )


        return list(
            result.scalars().all()
        )



    def get_by_target_entity(
        self,
        entity_id: UUID,
    ) -> list[EntityMerge]:
        """
        Return merges where entity
        became target.
        """

        result = self.session.execute(
            select(EntityMerge)
            .where(
                EntityMerge.target_entity_id
                ==
                entity_id
            )
        )


        return list(
            result.scalars().all()
        )



    def get_history_for_entity(
        self,
        entity_id: UUID,
    ) -> list[EntityMerge]:
        """
        Return all merge operations
        involving entity.
        """

        result = self.session.execute(
            select(EntityMerge)
            .where(
                (
                    EntityMerge.source_entity_id
                    ==
                    entity_id
                )
                |
                (
                    EntityMerge.target_entity_id
                    ==
                    entity_id
                )
            )
        )


        return list(
            result.scalars().all()
        )