"""
Tests for HTMLExporter.
"""


from app.exporters.html_exporter import (
    HTMLExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



def test_html_export():

    exporter = HTMLExporter()


    report = InvestigationReport(
        title="Investigation Test",
        summary="Test summary",
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


    assert (
        "<html>"
        in
        result
    )


    assert (
        "Investigation Test"
        in
        result
    )


    assert (
        "John"
        in
        result
    )



def test_html_exporter_metadata():

    exporter = HTMLExporter()


    metadata = (
        exporter.metadata()
    )


    assert (
        metadata["type"]
        ==
        "html_exporter"
    )


    assert (
        metadata["format"]
        ==
        "html"
    )