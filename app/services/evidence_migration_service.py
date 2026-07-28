"""
Evidence migration service.

Moves evidence links from one entity
to another during entity merge.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence_entity import (
    EvidenceEntity,
)


class EvidenceMigrationService:
    """
    Migrates evidence relations.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.session = session


    def migrate_evidence_links(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> int:
        """
        Move evidence links.

        Returns number of migrated links.
        """

        links = self.session.execute(
            select(EvidenceEntity)
            .where(
                EvidenceEntity.entity_id
                ==
                source_entity_id
            )
        ).scalars().all()


        migrated = 0


        for link in links:

            existing = self.session.execute(
                select(EvidenceEntity)
                .where(
                    EvidenceEntity.evidence_id
                    ==
                    link.evidence_id,
                    EvidenceEntity.entity_id
                    ==
                    target_entity_id,
                )
            ).scalar_one_or_none()


            if existing:
                self.session.delete(
                    link
                )

            else:
                link.entity_id = (
                    target_entity_id
                )

            migrated += 1


        self.session.flush()


        return migrated