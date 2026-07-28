"""
JSON report exporter.

Converts InvestigationReport
into JSON representation.

Responsibilities:

- serialize report
- return JSON string

Does NOT:

- write files
- modify reports
- access database
"""

from __future__ import annotations


import json

from typing import Any


from app.exporters.base import (
    BaseExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



class JSONExporter(
    BaseExporter
):
    """
    Exports reports as JSON.
    """



    # ==========================================================
    # Export
    # ==========================================================

    def export(
        self,
        report: InvestigationReport,
    ) -> str:
        """
        Convert report to JSON string.
        """


        return json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=4,
        )



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Exporter metadata.
        """

        return {

            "type":
                "json_exporter",

            "version":
                "1.0",

            "format":
                "json",

        }