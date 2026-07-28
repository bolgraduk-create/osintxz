"""
Report repository.

Provides database operations
for investigation reports.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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