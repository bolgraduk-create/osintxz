"""
Source repository.

Provides database operations
for imported information sources.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import (
    Source,
    SourceStatus,
    SourceType,
)

from app.repositories.base_repository import (
    BaseRepository,
)


class SourceRepository(
    BaseRepository[Source],
):
    """
    Repository for Source model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Source,
        )


    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Source]:
        """
        Return all sources
        belonging to a case.
        """

        result = self.session.execute(
            select(Source)
            .where(
                Source.case_id == case_id
            )
        )

        return list(
            result.scalars().all()
        )


    def get_by_type(
        self,
        source_type: SourceType,
    ) -> list[Source]:
        """
        Find sources by type.
        """

        result = self.session.execute(
            select(Source)
            .where(
                Source.source_type == source_type
            )
        )

        return list(
            result.scalars().all()
        )


    def get_by_status(
        self,
        status: SourceStatus,
    ) -> list[Source]:
        """
        Find sources by import status.
        """

        result = self.session.execute(
            select(Source)
            .where(
                Source.status == status
            )
        )

        return list(
            result.scalars().all()
        )


    def update_status(
        self,
        source_id: UUID,
        status: SourceStatus,
    ) -> Source | None:
        """
        Update import status.
        """

        source = self.get(
            source_id
        )

        if source is None:
            return None

        source.status = status

        self.session.flush()

        return source