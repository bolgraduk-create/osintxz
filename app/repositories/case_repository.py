"""
Case repository.

Provides database operations
for investigation cases.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.repositories.base_repository import BaseRepository


class CaseRepository(
    BaseRepository[Case],
):
    """
    Repository for Case model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Case,
        )

    def create_case(
        self,
        title: str,
        description: str = "",
    ) -> Case:
        """
        Create new investigation case.
        """

        case = Case(
            title=title,
            description=description,
        )

        self.session.add(case)
        self.session.flush()

        return case

    def get_by_title(
        self,
        title: str,
    ) -> Case | None:
        """
        Find case by title.
        """

        result = self.session.execute(
            select(Case).where(
                Case.title == title,
            )
        )

        return result.scalar_one_or_none()

    def get_active_cases(
        self,
    ) -> list[Case]:
        """
        Return all active (not deleted) cases.
        """

        result = self.session.execute(
            select(Case).where(
                Case.deleted_at.is_(None),
            )
        )

        return list(
            result.scalars().all()
        )

    def delete_by_id(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Soft delete case.
        """

        case = self.get(case_id)

        if case is None:
            return False

        case.soft_delete()

        self.session.flush()

        return True