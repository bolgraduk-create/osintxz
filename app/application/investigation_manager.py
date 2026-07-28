"""
Investigation manager.

Coordinates investigation workflow.

Responsibilities:

- orchestrate existing services
- manage investigation flow
- connect analysis and reporting

Does NOT:

- perform analysis
- call AI directly
- generate reports directly
- access database directly
"""

from __future__ import annotations


from typing import Any


from app.reporting.generator import (
    ReportGenerator,
)



class InvestigationManager:
    """
    Main application coordinator.
    """


    def __init__(
        self,
        report_generator: ReportGenerator | None = None,
    ):
        self.report_generator = (
            report_generator
            or ReportGenerator()
        )



    # ==========================================================
    # Workflow
    # ==========================================================

    def create_report(
        self,
        analysis_result: dict[str, Any],
    ):
        """
        Create investigation report
        from analysis result.
        """


        return self.report_generator.generate(
            analysis_result
        )



    def run(
        self,
        investigation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute basic investigation workflow.

        Current version:
        analysis result -> report
        """


        report = (
            self.create_report(
                investigation_data
            )
        )


        return {

            "report":
                report,

            "status":
                "completed",

        }



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Manager metadata.
        """

        return {

            "type":
                "investigation_manager",

            "version":
                "1.0",

        }