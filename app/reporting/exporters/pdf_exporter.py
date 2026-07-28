"""
PDF report exporter.

Currently provides a plain-text PDF representation.

Future versions can support
tables, styling and images.
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate

from app.reporting.exporters.base_exporter import (
    BaseReportExporter,
)

from app.reporting.models import (
    InvestigationReport,
)


class PdfReportExporter(
    BaseReportExporter,
):
    """
    Exports report to PDF.

    Returns PDF bytes.
    """

    def export(
        self,
        report: InvestigationReport,
    ) -> bytes:

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
        )

        styles = getSampleStyleSheet()

        story = []

        story.append(
            Paragraph(
                report.title,
                styles["Heading1"],
            )
        )

        story.append(
            Paragraph(
                report.summary,
                styles["BodyText"],
            )
        )

        if report.findings:

            story.append(
                Paragraph(
                    "Findings",
                    styles["Heading2"],
                )
            )

            for item in report.findings:

                story.append(
                    Paragraph(
                        str(item),
                        styles["BodyText"],
                    )
                )

        if report.evidence:

            story.append(
                Paragraph(
                    "Evidence",
                    styles["Heading2"],
                )
            )

            for item in report.evidence:

                story.append(
                    Paragraph(
                        str(item),
                        styles["BodyText"],
                    )
                )

        if report.ai_insights:

            story.append(
                Paragraph(
                    "AI Insights",
                    styles["Heading2"],
                )
            )

            for item in report.ai_insights:

                story.append(
                    Paragraph(
                        str(item),
                        styles["BodyText"],
                    )
                )

        document.build(story)

        pdf = buffer.getvalue()

        buffer.close()

        return pdf