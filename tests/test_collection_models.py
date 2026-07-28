"""
Tests for collection models.
"""


from app.collection.models import (
    CollectedData,
)



def test_collected_data_creation():

    data = CollectedData(

        source="telegram",

        content="test message",

        metadata={
            "type":
                "message"
        },

    )


    assert (
        data.source
        ==
        "telegram"
    )


    assert (
        data.content
        ==
        "test message"
    )


    assert (
        data.metadata["type"]
        ==
        "message"
    )



def test_collected_data_to_dict():

    data = CollectedData(

        source="file",

        content="document",

    )


    result = data.to_dict()


    assert (
        result["source"]
        ==
        "file"
    )


    assert (
        result["content"]
        ==
        "document"
    )


    assert (
        "collected_at"
        in
        result
    )