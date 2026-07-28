"""
Tests for TelegramCollector.
"""


import json


from app.collection.telegram_collector import (
    TelegramCollector,
)



def test_telegram_collection(
    tmp_path,
):

    export = tmp_path / "result.json"


    data = {

        "messages":

        [

            {

                "from":
                    "John",

                "text":
                    "Hello",

                "date":
                    "2026-01-01",

                "type":
                    "message",

            }

        ]

    }


    export.write_text(
        json.dumps(data),
        encoding="utf-8",
    )


    collector = TelegramCollector()


    result = collector.collect(
        export
    )


    assert (
        result.source
        ==
        "telegram"
    )


    assert (
        result.metadata["message_count"]
        ==
        1
    )


    assert (
        "John"
        in
        result.metadata["users"]
    )


    assert (
        result.content[0]["text"]
        ==
        "Hello"
    )



def test_invalid_telegram_file(
    tmp_path,
):

    file = tmp_path / "test.txt"


    file.write_text(
        "test",
        encoding="utf-8",
    )


    collector = TelegramCollector()


    try:

        collector.collect(
            file
        )

        assert False


    except ValueError:

        assert True