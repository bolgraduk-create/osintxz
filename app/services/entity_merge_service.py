"""
Entity merge service.

Handles entity merge operations
and keeps merge history.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entity import Entity

from app.models.entity_merge import EntityMerge

from app.repositories.entity_merge_repository import (
    EntityMergeRepository,
)


class EntityMergeService:
    """
    Service for merging entities.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self.repository = EntityMergeRepository(
            session
        )


    def merge_entities(
        self,
        source_entity: Entity,
        target_entity: Entity,
        reason: str | None = None,
    ) -> EntityMerge:
        """
        Create entity merge record.

        Source entity becomes merged
        into target entity.
        """

        if (
            source_entity.id
            ==
            target_entity.id
        ):
            raise ValueError(
                "Cannot merge entity into itself"
            )


        merge = EntityMerge(
            source_entity_id=source_entity.id,
            target_entity_id=target_entity.id,
            reason=reason,
        )


        self.session.add(
            merge
        )

        self.session.flush()


        return merge