"""
Report repository.

Provides database operations
for investigation reports.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.repositories.base_repository import BaseRepository


class ReportRepository(
    BaseRepository[Report],
):
    """
    Repository for Report model.
    """


    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Report,
        )


    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Report]:
        """
        Return all reports for a case.
        """

        result = self.session.execute(
            select(Report)
            .where(
                Report.case_id == case_id
            )
        )

        return list(
            result.scalars().all()
        )


    def get_page(self, *, limit: int = 100, offset: int = 0, case_id: UUID | None = None) -> list[Report]:
        statement = (
            select(Report)
            .where(Report.deleted_at.is_(None))
            .order_by(Report.created_at, Report.id)
            .offset(max(0, int(offset)))
            .limit(max(1, min(int(limit), 500)))
        )
        if case_id is not None:
            statement = statement.where(Report.case_id == case_id)
        return list(self.session.scalars(statement).all())

    def count_all(self, *, case_id: UUID | None = None) -> int:
        statement = select(func.count(Report.id))
        statement = statement.where(Report.deleted_at.is_(None))
        if case_id is not None:
            statement = statement.where(Report.case_id == case_id)
        return int(self.session.scalar(statement) or 0)

    def get_by_type(
        self,
        report_type,
    ) -> list[Report]:
        """
        Return reports by type.
        """

        result = self.session.execute(
            select(Report)
            .where(
                Report.report_type == report_type
            )
        )

        return list(
            result.scalars().all()
        )
