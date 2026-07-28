"""
Analysis service test.
"""


def test_analysis_service():

    from app.services import (
        AnalysisService,
    )


    service = AnalysisService()


    result = service.analyze(
        {
            "text": "hello test@example.com",
            "messages": [],
            "events": [],
        }
    )


    assert "entities" in result
    assert "sentiment" in result