"""
Report service.

Contains business logic related
to investigation reports.

Report generation itself is handled
by separate report modules.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.report import (
    Report,
    ReportType,
)

from app.repositories.report_repository import (
    ReportRepository,
)


class ReportService:
    """
    Service for managing reports.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = ReportRepository(
            session
        )

    def create_report(
        self,
        case_id: UUID,
        title: str,
        content: str,
        report_type: ReportType,
        description: str | None = None,
    ) -> Report:
        """
        Create new report.
        """

        report = Report(
            case_id=case_id,
            title=title,
            content=content,
            report_type=report_type,
            description=description,
        )

        return self.repository.create(
            report
        )

    def get_report(
        self,
        report_id: UUID,
    ) -> Report | None:
        """
        Get report by id.
        """

        return self.repository.get(
            report_id
        )

    def get_case_reports(
        self,
        case_id: UUID,
    ) -> list[Report]:
        """
        Return reports for case.
        """

        return self.repository.get_by_case(
            case_id
        )

    def update_content(
        self,
        report_id: UUID,
        content: str,
    ) -> Report | None:
        """
        Update report content.
        """

        report = self.repository.get(
            report_id
        )

        if report is None:
            return None

        report.content = content

        self.repository.session.flush()

        return report

    def delete_report(
        self,
        report_id: UUID,
    ) -> bool:
        """
        Soft delete report.
        """

        report = self.repository.get(
            report_id
        )

        if report is None:
            return False

        report.soft_delete()

        self.repository.session.flush()

        return True