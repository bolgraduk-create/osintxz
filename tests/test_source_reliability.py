"""
Tests for source reliability.
"""


from app.evidence.reliability import (
    SourceReliability,
    SourceReliabilityLevel,
)



def test_known_source_score():

    service = SourceReliability()


    score = service.get_score(
        "official_document"
    )


    assert (
        score
        ==
        0.95
    )



def test_unknown_source_score():

    service = SourceReliability()


    score = service.get_score(
        "something_unknown"
    )


    assert (
        score
        ==
        0.3
    )



def test_reliability_level():

    service = SourceReliability()


    assert (
        service.get_level(
            0.9
        )
        ==
        SourceReliabilityLevel.HIGH
    )


    assert (
        service.get_level(
            0.6
        )
        ==
        SourceReliabilityLevel.MEDIUM
    )


    assert (
        service.get_level(
            0.2
        )
        ==
        SourceReliabilityLevel.LOW
    )