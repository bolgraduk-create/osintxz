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
    ) -> None:
        self.repository = ReportRepository(
            session
        )

    # ==========================================================
    # Create
    # ==========================================================

    def create_report(
        self,
        case_id: UUID,
        title: str,
        content: str,
        report_type: ReportType,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Report:
        """
        Create a new report.
        """

        report = Report(
            case_id=case_id,
            title=title,
            content=content,
            report_type=report_type,
            metadata_json=metadata_json,
            description=description,
        )

        return self.repository.create(
            report
        )

    # ==========================================================
    # Read
    # ==========================================================

    def get_report(
        self,
        report_id: UUID,
    ) -> Report | None:
        """
        Get report by ID.
        """

        return self.repository.get(
            report_id
        )

    def get_case_reports(
        self,
        case_id: UUID,
    ) -> list[Report]:
        """
        Return reports belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )

    def get_case_report_by_type(
        self,
        case_id: UUID,
        report_type: ReportType,
    ) -> Report | None:
        """
        Return the first active report of a given
        type belonging to the case.

        The current reports architecture keeps
        one automatically generated report of
        each type for a case.
        """

        reports = self.repository.get_by_case(
            case_id
        )

        for report in reports:
            if report.report_type != report_type:
                continue

            is_deleted = getattr(
                report,
                "is_deleted",
                False,
            )

            if is_deleted:
                continue

            return report

        return None

    # ==========================================================
    # Update
    # ==========================================================

    def update_report(
        self,
        report_id: UUID,
        title: str,
        content: str,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Report | None:
        """
        Update an existing report.
        """

        report = self.repository.get(
            report_id
        )

        if report is None:
            return None

        report.title = title
        report.content = content
        report.metadata_json = metadata_json
        report.description = description

        self.repository.session.flush()

        return report

    def update_content(
        self,
        report_id: UUID,
        content: str,
    ) -> Report | None:
        """
        Update only report content.
        """

        report = self.repository.get(
            report_id
        )

        if report is None:
            return None

        report.content = content

        self.repository.session.flush()

        return report

    # ==========================================================
    # Delete
    # ==========================================================

    def delete_report(
        self,
        report_id: UUID,
    ) -> bool:
        """
        Soft-delete a report.
        """

        report = self.repository.get(
            report_id
        )

        if report is None:
            return False

        report.soft_delete()

        self.repository.session.flush()

        return True