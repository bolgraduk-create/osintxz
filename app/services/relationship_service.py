"""
Relationship service.

Contains business logic related
to relationships between entities.

Examples:

- Person knows Person
- Account belongs to Person
- Phone connected to Account
- Organization related to Person
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.relationship import (
    Relationship,
    RelationshipType,
)

from app.repositories.relationship_repository import (
    RelationshipRepository,
)


class RelationshipService:
    """
    Service for managing entity relationships.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = RelationshipRepository(
            session
        )

    def create_relationship(
        self,
        case_id: UUID,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: RelationshipType,
        confidence: float = 1.0,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Relationship:
        """
        Create entity relationship.
        """

        relationship = Relationship(
            case_id=case_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            confidence=confidence,
            metadata_json=metadata_json,
            description=description,
        )

        return self.repository.create(
            relationship
        )

    def get_relationship(
        self,
        relationship_id: UUID,
    ) -> Relationship | None:
        """
        Get relationship by id.
        """

        return self.repository.get(
            relationship_id
        )

    def get_case_relationships(
        self,
        case_id: UUID,
    ) -> list[Relationship]:
        """
        Return relationships
        belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )

    def get_entity_relationships(
        self,
        entity_id: UUID,
    ) -> list[Relationship]:
        """
        Return all relationships
        where entity participates.
        """

        return self.repository.get_entity_connections(
            entity_id
        )

    def update_confidence(
        self,
        relationship_id: UUID,
        confidence: float,
    ) -> Relationship | None:
        """
        Update confidence score.
        """

        relationship = self.repository.get(
            relationship_id
        )

        if relationship is None:
            return None

        relationship.confidence = confidence

        self.repository.session.flush()

        return relationship

    def delete_relationship(
        self,
        relationship_id: UUID,
    ) -> bool:
        """
        Soft delete relationship.
        """

        relationship = self.repository.get(
            relationship_id
        )

        if relationship is None:
            return False

        relationship.soft_delete()

        self.repository.session.flush()

        return True