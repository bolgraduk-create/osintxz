"""
Report generator.

Builds structured investigation reports
from analysis results.

Responsibilities:

- combine analysis data
- create InvestigationReport
- prepare intelligence output

Does NOT:

- save reports
- export files
- run AI models
"""

from __future__ import annotations


from typing import Any


from app.reporting.models import (
    InvestigationReport,
)



class ReportGenerator:
    """
    Generates investigation reports.
    """


    def __init__(
        self,
    ):
        pass



    # ==========================================================
    # Main generation
    # ==========================================================

    def generate(
        self,
        data: dict[str, Any],
    ) -> InvestigationReport:
        """
        Generate investigation report.
        """


        report = InvestigationReport(
            title=(
                data.get(
                    "title",
                    "Investigation Report",
                )
            ),

            summary=(
                data.get(
                    "summary",
                    "",
                )
            ),
        )


        report.findings = (
            self.extract_findings(
                data
            )
        )


        report.evidence = (
            self.extract_evidence(
                data
            )
        )


        report.ai_insights = (
            self.extract_ai_insights(
                data
            )
        )


        report.metadata = (
            self.extract_metadata(
                data
            )
        )


        return report



    # ==========================================================
    # Extractors
    # ==========================================================

    def extract_findings(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extract investigation findings.
        """


        return (
            data.get(
                "findings",
                [],
            )
        )



    def extract_evidence(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extract evidence.
        """


        return (
            data.get(
                "evidence",
                [],
            )
        )



    def extract_ai_insights(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extract AI conclusions.
        """


        return (
            data.get(
                "ai_insights",
                [],
            )
        )



    def extract_metadata(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract report metadata.
        """


        return (
            data.get(
                "metadata",
                {},
            )
        )



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Generator metadata.
        """

        return {

            "type":
                "report_generator",

            "version":
                "1.0",

        }