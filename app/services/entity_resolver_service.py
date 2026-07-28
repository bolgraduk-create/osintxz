"""
Entity resolver service.

Coordinates entity comparison
and merging.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entity import Entity

from app.entity_resolution.comparator import (
    EntityComparator,
)

from app.services.entity_merge_service import (
    EntityMergeService,
)



class EntityResolverService:
    """
    Main entity resolution service.
    """


    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self.comparator = EntityComparator()

        self.merge_service = EntityMergeService(
            session
        )


    def are_same_entity(
        self,
        first: Entity,
        second: Entity,
    ) -> bool:
        """
        Check whether two entities
        represent the same object.
        """

        if (
            first.entity_type
            !=
            second.entity_type
        ):
            return False


        return self.comparator.compare(
            first.entity_type,
            first.value,
            second.value,
        )


    def resolve(
        self,
        source: Entity,
        target: Entity,
    ):
        """
        Resolve two entities.

        If they are duplicates,
        create merge record.
        """

        if not self.are_same_entity(
            source,
            target,
        ):
            return None


        return self.merge_service.merge_entities(
            source,
            target,
            reason="automatic entity resolution",
        )