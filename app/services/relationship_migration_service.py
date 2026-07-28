"""
Relationship migration service.

Moves relationships from one entity
to another during entity merge.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.relationship_repository import (
    RelationshipRepository,
)


class RelationshipMigrationService:
    """
    Migrates relationships between entities.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self.repository = RelationshipRepository(
            session
        )


    def migrate_relationships(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> int:
        """
        Replace source entity references
        with target entity.

        Returns number of migrated
        relationships.
        """

        relationships = (
            self.repository.get_entity_connections(
                source_entity_id
            )
        )


        migrated = 0


        for relationship in relationships:

            changed = False


            if (
                relationship.source_entity_id
                ==
                source_entity_id
            ):
                relationship.source_entity_id = (
                    target_entity_id
                )

                changed = True


            if (
                relationship.target_entity_id
                ==
                source_entity_id
            ):
                relationship.target_entity_id = (
                    target_entity_id
                )

                changed = True


            if changed:
                migrated += 1


        self.session.flush()


        return migrated