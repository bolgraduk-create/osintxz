"""
Tests for investigation report model.
"""


from app.reporting.models import (
    InvestigationReport,
)



def test_report_creation():

    report = InvestigationReport(
        title="Test Investigation"
    )


    assert (
        report.title
        ==
        "Test Investigation"
    )


    assert (
        report.findings
        ==
        []
    )



def test_report_serialization():

    report = InvestigationReport(
        title="Test Report",
        summary="Summary",
    )


    data = report.to_dict()


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


    assert (
        "created_at"
        in
        data
    )