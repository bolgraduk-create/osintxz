"""
Markdown report exporter.
"""

from __future__ import annotations

from app.reporting.exporters.base_exporter import (
    BaseReportExporter,
)

from app.reporting.models import (
    InvestigationReport,
)


class MarkdownReportExporter(
    BaseReportExporter,
):
    """
    Exports investigation report
    as Markdown.
    """

    def export(
        self,
        report: InvestigationReport,
    ) -> str:

        lines: list[str] = []

        lines.append(f"# {report.title}")
        lines.append("")

        if report.summary:
            lines.append("## Summary")
            lines.append(report.summary)
            lines.append("")

        if report.findings:
            lines.append("## Findings")

            for finding in report.findings:
                lines.append(
                    f"- {finding}"
                )

            lines.append("")

        if report.evidence:
            lines.append("## Evidence")

            for evidence in report.evidence:
                lines.append(
                    f"- {evidence}"
                )

            lines.append("")

        if report.ai_insights:
            lines.append("## AI Insights")

            for insight in report.ai_insights:
                lines.append(
                    f"- {insight}"
                )

            lines.append("")

        if report.metadata:
            lines.append("## Metadata")

            for key, value in report.metadata.items():
                lines.append(
                    f"- **{key}**: {value}"
                )

            lines.append("")

        return "\n".join(lines)