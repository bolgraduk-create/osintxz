"""
JSON report exporter.
"""

from __future__ import annotations

import json

from app.reporting.exporters.base_exporter import (
    BaseReportExporter,
)

from app.reporting.models import (
    InvestigationReport,
)


class JsonReportExporter(
    BaseReportExporter,
):
    """
    Exports report to JSON.
    """

    def export(
        self,
        report: InvestigationReport,
    ) -> str:
        """
        Export report as JSON string.
        """

        return json.dumps(
            report.to_dict(),
            indent=4,
            ensure_ascii=False,
        )