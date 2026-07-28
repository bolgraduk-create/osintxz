"""
Integration tests for reporting pipeline.
"""


import json


from app.reporting.generator import (
    ReportGenerator,
)


from app.exporters.json_exporter import (
    JSONExporter,
)


from app.exporters.html_exporter import (
    HTMLExporter,
)


from app.exporters.pdf_exporter import (
    PDFExporter,
)



def test_full_reporting_pipeline():

    # ==========================================
    # Create report
    # ==========================================

    generator = ReportGenerator()


    report = generator.generate(
        {

            "title":
                "OSINT Investigation",


            "summary":
                "Integration test report",


            "findings":
                [
                    {
                        "entity":
                            "John"
                    }
                ],


            "evidence":
                [
                    {
                        "source":
                            "telegram"
                    }
                ],


            "ai_insights":
                [
                    {
                        "risk":
                            "low"
                    }
                ],

        }
    )


    assert (
        report.title
        ==
        "OSINT Investigation"
    )


    # ==========================================
    # JSON export
    # ==========================================

    json_exporter = JSONExporter()


    json_result = (
        json_exporter.export(
            report
        )
    )


    json_data = json.loads(
        json_result
    )


    assert (
        json_data["title"]
        ==
        "OSINT Investigation"
    )



    # ==========================================
    # HTML export
    # ==========================================

    html_exporter = HTMLExporter()


    html_result = (
        html_exporter.export(
            report
        )
    )


    assert (
        "<html>"
        in
        html_result
    )


    assert (
        "John"
        in
        html_result
    )



    # ==========================================
    # PDF export
    # ==========================================

    pdf_exporter = PDFExporter()


    pdf_result = (
        pdf_exporter.export(
            report
        )
    )


    assert isinstance(
        pdf_result,
        bytes,
    )


    assert (
        pdf_result.startswith(
            b"%PDF"
        )
    )