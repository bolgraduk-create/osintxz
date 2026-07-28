"""
Full integration test for Analysis Layer.
"""

from app.services.analysis_service import (
    AnalysisService,
)


def test_analysis_full_flow():

    service = AnalysisService()


    result = service.analyze(
        {
            "text": (
                "John contacted Alice. "
                "The situation is good."
            ),

            "messages": [
                {
                    "sender": "John",
                    "receiver": "Alice",
                    "text": "Hello Alice",
                },
                {
                    "sender": "Alice",
                    "receiver": "John",
                    "text": "Thanks John",
                },
            ],

            "events": [
                {
                    "id": 1,
                    "type": "message",
                    "timestamp":
                        "2026-01-01T12:00:00",
                    "title":
                        "First contact",
                }
            ],
        }
    )


    assert result is not None

    assert "entities" in result

    assert "relationships" in result

    assert "timeline" in result

    assert "sentiment" in result

    assert "metadata" in result


    assert (
        "modules"
        in result["metadata"]
    )