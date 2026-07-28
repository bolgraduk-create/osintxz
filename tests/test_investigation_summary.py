"""
Tests for InvestigationSummaryBuilder.
"""


from app.reporting.summary import (
    InvestigationSummaryBuilder,
)



def test_build_summary():

    builder = (
        InvestigationSummaryBuilder()
    )


    summary = builder.build(
        {
            "subject":
                "John Investigation",


            "timeline":
                [
                    {
                        "date":
                            "2026-01-01"
                    }
                ],


            "entities":
                [
                    {
                        "name":
                            "John"
                    }
                ],


            "relationships":
                [
                    {
                        "type":
                            "connection"
                    }
                ],


            "findings":
                [
                    {
                        "result":
                            "connected"
                    }
                ],


            "ai_conclusions":
                [
                    {
                        "risk":
                            "low"
                    }
                ],
        }
    )


    assert (
        summary["subject"]
        ==
        "John Investigation"
    )


    assert len(
        summary["timeline"]
    ) == 1


    assert len(
        summary["entities"]
    ) == 1


    assert len(
        summary["relationships"]
    ) == 1



def test_summary_metadata():

    builder = (
        InvestigationSummaryBuilder()
    )


    metadata = (
        builder.metadata()
    )


    assert (
        metadata["type"]
        ==
        "investigation_summary_builder"
    )


    assert (
        metadata["version"]
        ==
        "1.0"
    )