"""
Analysis pipeline test.
"""


def test_analysis_pipeline():

    from app.analysis import (
        AnalysisPipeline,
    )


    pipeline = AnalysisPipeline()


    result = pipeline.analyze(
        {
            "text": "hello test@example.com",
            "messages": [],
            "events": [],
        }
    )


    assert "entities" in result
    assert "relationships" in result
    assert "timeline" in result
    assert "sentiment" in result