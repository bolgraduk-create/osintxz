"""
Tests for PDFExporter.
"""


from app.exporters.pdf_exporter import (
    PDFExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



def test_pdf_export():

    exporter = PDFExporter()


    report = InvestigationReport(
        title="PDF Test",
        summary="PDF Summary",
        findings=[
            {
                "entity":
                    "John"
            }
        ],
    )


    result = exporter.export(
        report
    )


    assert isinstance(
        result,
        bytes,
    )


    assert (
        result.startswith(
            b"%PDF"
        )
    )



def test_pdf_exporter_metadata():

    exporter = PDFExporter()


    metadata = (
        exporter.metadata()
    )


    assert (
        metadata["type"]
        ==
        "pdf_exporter"
    )


    assert (
        metadata["format"]
        ==
        "pdf"
    )