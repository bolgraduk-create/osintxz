"""
Evidence repository.

Provides database operations
for extracted evidence objects.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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

    def get_page(self, *, limit: int = 100, offset: int = 0, case_id: UUID | None = None) -> list[Evidence]:
        statement = (
            select(Evidence)
            .where(Evidence.deleted_at.is_(None))
            .order_by(Evidence.created_at, Evidence.id)
            .offset(max(0, int(offset)))
            .limit(max(1, min(int(limit), 500)))
        )
        if case_id is not None:
            statement = statement.where(Evidence.case_id == case_id)
        return list(self.session.scalars(statement).all())

    def count_all(self, *, case_id: UUID | None = None) -> int:
        statement = select(func.count(Evidence.id))
        statement = statement.where(Evidence.deleted_at.is_(None))
        if case_id is not None:
            statement = statement.where(Evidence.case_id == case_id)
        return int(self.session.scalar(statement) or 0)

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

    def find_by_case_and_hash(
        self,
        case_id: UUID,
        sha256: str,
    ) -> Evidence | None:
        """
        Find active evidence by SHA256 inside one case.
        """

        normalized_hash = str(
            sha256
            or ""
        ).strip().lower()

        if not normalized_hash:

            return None

        result = self.session.execute(
            select(Evidence)
            .where(
                Evidence.case_id == case_id,
                Evidence.sha256 == normalized_hash,
                Evidence.deleted_at.is_(None),
            )
            .limit(1)
        )

        return result.scalar_one_or_none()

    def search_case_structured(
        self,
        case_id: UUID,
        *,
        evidence_types: tuple[EvidenceType, ...] = (),
        object_ids: tuple[UUID, ...] = (),
        source_ids: tuple[UUID, ...] = (),
        values: tuple[str, ...] = (),
        include_deleted: bool = False,
        limit: int = 200,
    ) -> list[Evidence]:
        """Return Evidence rows matching explicit structured filters."""

        statement = select(Evidence).where(Evidence.case_id == case_id)

        if not include_deleted:
            statement = statement.where(Evidence.deleted_at.is_(None))

        if evidence_types:
            statement = statement.where(Evidence.evidence_type.in_(evidence_types))

        if object_ids:
            statement = statement.where(Evidence.id.in_(object_ids))

        if source_ids:
            statement = statement.where(Evidence.source_id.in_(source_ids))

        if values:
            statement = statement.where(Evidence.value.in_(values))

        statement = statement.order_by(
            Evidence.created_at.desc(),
            Evidence.id,
        ).limit(max(1, int(limit)))

        result = self.session.execute(statement)
        return list(result.scalars().all())
