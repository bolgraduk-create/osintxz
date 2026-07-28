"""
Analysis layer import test.
"""


def test_analysis_imports():

    from app.analysis.analyzers import (
        EntityAnalyzer,
        RelationshipAnalyzer,
        TimelineAnalyzer,
        SentimentAnalyzer,
    )


    assert EntityAnalyzer
    assert RelationshipAnalyzer
    assert TimelineAnalyzer
    assert SentimentAnalyzer