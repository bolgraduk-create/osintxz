"""
Evidence linking service.

Handles relations between evidence
objects and entities.
"""

from __future__ import annotations


from uuid import UUID


from sqlalchemy import select
from sqlalchemy.orm import Session


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
    ):
        self.session = session



    def link_evidence_to_entity(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> EvidenceEntity:
        """
        Create evidence-entity link.
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



    def unlink_evidence_from_entity(
        self,
        evidence_id: UUID,
        entity_id: UUID,
    ) -> bool:
        """
        Remove evidence-entity link.
        """

        result = self.session.execute(
            select(EvidenceEntity)
            .where(
                EvidenceEntity.evidence_id
                ==
                evidence_id,
                EvidenceEntity.entity_id
                ==
                entity_id,
            )
        )


        link = result.scalar_one_or_none()


        if link is None:
            return False


        self.session.delete(
            link
        )

        self.session.flush()


        return True



    def get_entities_for_evidence(
        self,
        evidence_id: UUID,
    ) -> list[EvidenceEntity]:
        """
        Return entities connected
        to evidence.
        """

        result = self.session.execute(
            select(EvidenceEntity)
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
        Return evidence connected
        to entity.
        """

        result = self.session.execute(
            select(EvidenceEntity)
            .where(
                EvidenceEntity.entity_id
                ==
                entity_id
            )
        )


        return list(
            result.scalars().all()
        )