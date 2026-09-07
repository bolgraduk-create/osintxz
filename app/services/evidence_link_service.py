"""
Evidence linking service.

Handles relations between evidence
objects and entities.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.models.evidence_entity import (
    EvidenceEntity,
)


class EvidenceLinkService:
    """
    Service for evidence-entity links.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

    # ==========================================================
    # Link creation
    # ==========================================================

    def link_evidence_to_entity(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> EvidenceEntity:
        """
        Create evidence-entity link.

        This method keeps the original direct-create behavior.
        Use ensure_link() when duplicate-safe behavior is required.
        """

        link = EvidenceEntity(
            evidence_id=evidence_id,
            entity_id=entity_id,
        )

        self.session.add(
            link
        )

        self.session.flush()

        return link

    def ensure_link(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> tuple[EvidenceEntity, bool]:
        """
        Ensure evidence-entity link exists.

        Returns:
            tuple[EvidenceEntity, bool]:
                link object and whether it was newly created.
        """

        existing = self.get_link(
            evidence_id=evidence_id,
            entity_id=entity_id,
        )

        if existing is not None:

            return (
                existing,
                False,
            )

        link = self.link_evidence_to_entity(
            evidence_id=evidence_id,
            entity_id=entity_id,
        )

        return (
            link,
            True,
        )

    # ==========================================================
    # Link removal
    # ==========================================================

    def unlink_evidence_from_entity(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> bool:
        """
        Remove evidence-entity link.
        """

        link = self.get_link(
            evidence_id=evidence_id,
            entity_id=entity_id,
        )

        if link is None:

            return False

        self.session.delete(
            link
        )

        self.session.flush()

        return True

    # ==========================================================
    # Link lookup
    # ==========================================================

    def get_link(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> EvidenceEntity | None:
        """
        Return one exact evidence-entity link.
        """

        result = self.session.execute(
            select(
                EvidenceEntity
            )
            .where(
                EvidenceEntity.evidence_id
                ==
                evidence_id,
                EvidenceEntity.entity_id
                ==
                entity_id,
            )
            .limit(
                1
            )
        )

        return result.scalar_one_or_none()

    def has_link(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> bool:
        """
        Check whether evidence is already linked
        to the selected entity.
        """

        return (
            self.get_link(
                evidence_id=evidence_id,
                entity_id=entity_id,
            )
            is not None
        )

    # ==========================================================
    # Link retrieval
    # ==========================================================

    def get_entities_for_evidence(
        self,
        evidence_id: UUID,
    ) -> list[EvidenceEntity]:
        """
        Return entity links connected
        to evidence.
        """

        result = self.session.execute(
            select(
                EvidenceEntity
            )
            .where(
                EvidenceEntity.evidence_id
                ==
                evidence_id
            )
        )

        return list(
            result.scalars().all()
        )

    def get_evidence_for_entity(
        self,
        entity_id: UUID,
    ) -> list[EvidenceEntity]:
        """
        Return evidence links connected
        to entity.
        """

        result = self.session.execute(
            select(
                EvidenceEntity
            )
            .where(
                EvidenceEntity.entity_id
                ==
                entity_id
            )
        )

        return list(
            result.scalars().all()
        )

    # ==========================================================
    # Evidence object retrieval
    # ==========================================================

    def get_evidence_objects_for_entity(
        self,
        entity_id: UUID,
        *,
        evidence_type: EvidenceType | None = None,
        include_deleted: bool = False,
    ) -> list[Evidence]:
        """
        Return actual Evidence objects connected to entity.

        Optional evidence_type allows callers to request only
        images, documents, videos, etc.
        """

        statement = (
            select(
                Evidence
            )
            .join(
                EvidenceEntity,
                EvidenceEntity.evidence_id
                ==
                Evidence.id,
            )
            .where(
                EvidenceEntity.entity_id
                ==
                entity_id
            )
        )

        if evidence_type is not None:

            statement = statement.where(
                Evidence.evidence_type
                ==
                evidence_type
            )

        if not include_deleted:

            statement = statement.where(
                Evidence.deleted_at.is_(
                    None
                )
            )

        statement = statement.order_by(
            Evidence.created_at
        )

        result = self.session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    def get_image_evidence_for_entity(
        self,
        entity_id: UUID,
    ) -> list[Evidence]:
        """
        Return active IMAGE evidence connected
        to entity.
        """

        return (
            self.get_evidence_objects_for_entity(
                entity_id,
                evidence_type=(
                    EvidenceType.IMAGE
                ),
                include_deleted=False,
            )
        )