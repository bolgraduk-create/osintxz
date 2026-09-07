"""
Telegram report import service.

Generates and stores reports after
Telegram investigation data has been imported.

Responsibilities:

- build the investigation summary
- create the summary report when missing
- update the existing summary report
- return generation statistics

Does NOT:

- collect Telegram data
- import messages
- create entities
- create relationships
- create timeline events
- commit database transactions
- execute AI analysis
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.report import (
    Report,
    ReportType,
)

from app.services.investigation_summary_builder import (
    InvestigationSummaryBuilder,
)

from app.services.report_service import (
    ReportService,
)


class TelegramReportImportService:
    """
    Creates or updates reports after
    a Telegram import has completed.
    """

    def __init__(
        self,
        summary_builder: InvestigationSummaryBuilder,
        report_service: ReportService,
    ) -> None:
        self.summary_builder = summary_builder
        self.report_service = report_service

    # ==========================================================
    # Public API
    # ==========================================================

    def import_reports(
        self,
        case_id: UUID,
    ) -> dict[str, Any]:
        """
        Generate Telegram investigation reports.

        Currently generates one deterministic
        Investigation Summary report.

        Returns statistics in the form:

        {
            "found": int,
            "created": int,
            "updated": int,
            "skipped": int,
            "report_id": str | None,
        }
        """

        statistics: dict[str, Any] = {
            "found": 1,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "report_id": None,
        }

        summary_data = self.summary_builder.build(
            case_id
        )

        title = str(
            summary_data["title"]
        )

        content = str(
            summary_data["content"]
        )

        metadata_json = summary_data.get(
            "metadata_json"
        )

        existing_report = (
            self.report_service.get_case_report_by_type(
                case_id=case_id,
                report_type=ReportType.SUMMARY,
            )
        )

        if existing_report is None:
            report = self._create_summary_report(
                case_id=case_id,
                title=title,
                content=content,
                metadata_json=metadata_json,
            )

            statistics["created"] = 1
            statistics["report_id"] = str(
                report.id
            )

            return statistics

        if self._report_is_current(
            report=existing_report,
            title=title,
            content=content,
            metadata_json=metadata_json,
        ):
            statistics["skipped"] = 1
            statistics["report_id"] = str(
                existing_report.id
            )

            return statistics

        updated_report = self._update_summary_report(
            report=existing_report,
            title=title,
            content=content,
            metadata_json=metadata_json,
        )

        if updated_report is None:
            raise RuntimeError(
                "Existing summary report could not be updated."
            )

        statistics["updated"] = 1
        statistics["report_id"] = str(
            updated_report.id
        )

        return statistics

    # ==========================================================
    # Persistence
    # ==========================================================

    def _create_summary_report(
        self,
        case_id: UUID,
        title: str,
        content: str,
        metadata_json: str | None,
    ) -> Report:
        """
        Create a new investigation summary.
        """

        return self.report_service.create_report(
            case_id=case_id,
            title=title,
            content=content,
            report_type=ReportType.SUMMARY,
            metadata_json=metadata_json,
            description=(
                "Automatically generated deterministic "
                "summary of imported Telegram investigation data."
            ),
        )

    def _update_summary_report(
        self,
        report: Report,
        title: str,
        content: str,
        metadata_json: str | None,
    ) -> Report | None:
        """
        Update an existing investigation summary.
        """

        return self.report_service.update_report(
            report_id=report.id,
            title=title,
            content=content,
            metadata_json=metadata_json,
            description=(
                "Automatically generated deterministic "
                "summary of imported Telegram investigation data."
            ),
        )

    # ==========================================================
    # Comparison
    # ==========================================================

    def _report_is_current(
        self,
        report: Report,
        title: str,
        content: str,
        metadata_json: str | None,
    ) -> bool:
        """
        Check whether the stored report already
        contains the generated information.

        generated_at changes on every build, so
        metadata alone must not force an update.
        The content also contains generation time,
        therefore automatic imports currently
        refresh the report when the builder runs.

        This method remains separate so the comparison
        policy can later be replaced by a content hash.
        """

        return (
            report.title == title
            and report.content == content
            and report.metadata_json == metadata_json
        )