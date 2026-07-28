"""
Evidence repository.

Provides database operations
for extracted evidence objects.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import (
    Evidence,
    EvidenceType,
)
from app.repositories.base_repository import (
    BaseRepository,
)


class EvidenceRepository(
    BaseRepository[Evidence],
):
    """
    Repository for Evidence model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Evidence,
        )

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Evidence]:
        """
        Return evidence belonging to a case.
        """

        result = self.session.execute(
            select(Evidence)
            .where(
                Evidence.case_id == case_id,
            )
            .order_by(Evidence.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_source(
        self,
        source_id: UUID,
    ) -> list[Evidence]:
        """
        Return evidence imported from a source.
        """

        result = self.session.execute(
            select(Evidence)
            .where(
                Evidence.source_id == source_id,
            )
            .order_by(Evidence.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_type(
        self,
        evidence_type: EvidenceType,
    ) -> list[Evidence]:
        """
        Return evidence of a specific type.
        """

        result = self.session.execute(
            select(Evidence)
            .where(
                Evidence.evidence_type == evidence_type,
            )
            .order_by(Evidence.created_at)
        )

        return list(
            result.scalars().all()
        )

    def find_by_hash(
        self,
        sha256: str,
    ) -> Evidence | None:
        """
        Find evidence by SHA256 hash.
        """

        result = self.session.execute(
            select(Evidence)
            .where(
                Evidence.sha256 == sha256,
            )
        )

        return result.scalar_one_or_none()