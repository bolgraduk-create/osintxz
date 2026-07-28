"""
HTML report exporter.
"""

from __future__ import annotations

from html import escape

from app.reporting.exporters.base_exporter import (
    BaseReportExporter,
)

from app.reporting.models import (
    InvestigationReport,
)


class HtmlReportExporter(
    BaseReportExporter,
):
    """
    Exports investigation report
    as HTML.
    """

    def export(
        self,
        report: InvestigationReport,
    ) -> str:

        html: list[str] = []

        html.append(
            "<!DOCTYPE html>"
        )

        html.append("<html>")
        html.append("<head>")
        html.append("<meta charset='utf-8'>")
        html.append(
            f"<title>{escape(report.title)}</title>"
        )
        html.append("</head>")
        html.append("<body>")

        html.append(
            f"<h1>{escape(report.title)}</h1>"
        )

        if report.summary:
            html.append("<h2>Summary</h2>")
            html.append(
                f"<p>{escape(report.summary)}</p>"
            )

        if report.findings:
            html.append("<h2>Findings</h2>")
            html.append("<ul>")

            for finding in report.findings:
                html.append(
                    f"<li>{escape(str(finding))}</li>"
                )

            html.append("</ul>")

        if report.evidence:
            html.append("<h2>Evidence</h2>")
            html.append("<ul>")

            for evidence in report.evidence:
                html.append(
                    f"<li>{escape(str(evidence))}</li>"
                )

            html.append("</ul>")

        if report.ai_insights:
            html.append("<h2>AI Insights</h2>")
            html.append("<ul>")

            for insight in report.ai_insights:
                html.append(
                    f"<li>{escape(str(insight))}</li>"
                )

            html.append("</ul>")

        if report.metadata:
            html.append("<h2>Metadata</h2>")
            html.append("<ul>")

            for key, value in report.metadata.items():
                html.append(
                    f"<li><strong>{escape(str(key))}</strong>: {escape(str(value))}</li>"
                )

            html.append("</ul>")

        html.append("</body>")
        html.append("</html>")

        return "\n".join(html)