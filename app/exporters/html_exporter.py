"""
HTML report exporter.

Converts InvestigationReport
into HTML document.

Responsibilities:

- create HTML representation
- format report sections

Does NOT:

- write files
- modify reports
- access database
"""

from __future__ import annotations


from typing import Any


from html import escape


from app.exporters.base import (
    BaseExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



class HTMLExporter(
    BaseExporter
):
    """
    Exports reports as HTML.
    """



    # ==========================================================
    # Export
    # ==========================================================

    def export(
        self,
        report: InvestigationReport,
    ) -> str:
        """
        Convert report into HTML.
        """


        findings = (
            self.render_list(
                report.findings
            )
        )


        evidence = (
            self.render_list(
                report.evidence
            )
        )


        ai_insights = (
            self.render_list(
                report.ai_insights
            )
        )


        return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8">

<title>
{escape(report.title)}
</title>

</head>


<body>

<h1>
{escape(report.title)}
</h1>


<h2>
Summary
</h2>

<p>
{escape(report.summary)}
</p>



<h2>
Findings
</h2>

{findings}



<h2>
Evidence
</h2>

{evidence}



<h2>
AI Insights
</h2>

{ai_insights}


</body>

</html>
"""



    # ==========================================================
    # Helpers
    # ==========================================================

    def render_list(
        self,
        items: list[dict[str, Any]],
    ) -> str:
        """
        Render list items as HTML.
        """


        if not items:

            return (
                "<p>No data</p>"
            )


        html = "<ul>"


        for item in items:

            html += (
                "<li>"
                +
                escape(
                    str(item)
                )
                +
                "</li>"
            )


        html += "</ul>"


        return html



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
                "html_exporter",

            "version":
                "1.0",

            "format":
                "html",

        }