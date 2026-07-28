"""
PDF report exporter.

Converts InvestigationReport
into PDF document bytes.

Responsibilities:

- create PDF representation
- format report content

Does NOT:

- save files
- manage storage
- modify reports
"""

from __future__ import annotations


from io import BytesIO

from typing import Any


from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
)


from app.exporters.base import (
    BaseExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



class PDFExporter(
    BaseExporter
):
    """
    Exports reports as PDF.
    """



    # ==========================================================
    # Export
    # ==========================================================

    def export(
        self,
        report: InvestigationReport,
    ) -> bytes:
        """
        Convert report into PDF bytes.
        """


        buffer = BytesIO()


        document = SimpleDocTemplate(
            buffer
        )


        styles = (
            getSampleStyleSheet()
        )


        content = []


        content.append(
            Paragraph(
                report.title,
                styles["Title"],
            )
        )


        content.append(
            Spacer(
                1,
                12,
            )
        )


        content.append(
            Paragraph(
                report.summary,
                styles["BodyText"],
            )
        )


        content.append(
            Spacer(
                1,
                12,
            )
        )


        content.append(
            Paragraph(
                "Findings",
                styles["Heading2"],
            )
        )


        for item in report.findings:

            content.append(
                Paragraph(
                    str(item),
                    styles["BodyText"],
                )
            )


        content.append(
            Spacer(
                1,
                12,
            )
        )


        content.append(
            Paragraph(
                "Evidence",
                styles["Heading2"],
            )
        )


        for item in report.evidence:

            content.append(
                Paragraph(
                    str(item),
                    styles["BodyText"],
                )
            )


        content.append(
            Spacer(
                1,
                12,
            )
        )


        content.append(
            Paragraph(
                "AI Insights",
                styles["Heading2"],
            )
        )


        for item in report.ai_insights:

            content.append(
                Paragraph(
                    str(item),
                    styles["BodyText"],
                )
            )


        document.build(
            content
        )


        return (
            buffer.getvalue()
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
                "pdf_exporter",

            "version":
                "1.0",

            "format":
                "pdf",

        }