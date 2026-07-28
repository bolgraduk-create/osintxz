"""
Tests for Evidence model.
"""


from uuid import uuid4


import pytest


from app.evidence.models import (
    Evidence,
)



def test_evidence_creation():

    case_id = uuid4()


    evidence = Evidence(

        case_id=case_id,

        source="telegram",

        content="Test message",

        metadata={
            "type":
                "message"
        },

    )


    assert (
        evidence.source
        ==
        "telegram"
    )


    assert (
        evidence.content
        ==
        "Test message"
    )


    assert (
        evidence.metadata["type"]
        ==
        "message"
    )


    assert (
        evidence.reliability
        ==
        0.5
    )



def test_update_reliability():

    evidence = Evidence(

        case_id=uuid4(),

        source="file",

        content="document",

    )


    evidence.update_reliability(
        0.9
    )


    assert (
        evidence.reliability
        ==
        0.9
    )



def test_invalid_reliability():

    evidence = Evidence(

        case_id=uuid4(),

        source="file",

        content="document",

    )


    with pytest.raises(
        ValueError
    ):

        evidence.update_reliability(
            2
        )