"""
Tests for JSONExporter.
"""


import json


from app.exporters.json_exporter import (
    JSONExporter,
)


from app.reporting.models import (
    InvestigationReport,
)



def test_json_export():

    exporter = JSONExporter()


    report = InvestigationReport(
        title="Test Report",
        summary="Summary",
    )


    result = exporter.export(
        report
    )


    data = json.loads(
        result
    )


    assert (
        data["title"]
        ==
        "Test Report"
    )


    assert (
        data["summary"]
        ==
        "Summary"
    )



def test_json_exporter_metadata():

    exporter = JSONExporter()


    metadata = (
        exporter.metadata()
    )


    assert (
        metadata["type"]
        ==
        "json_exporter"
    )


    assert (
        metadata["format"]
        ==
        "json"
    )