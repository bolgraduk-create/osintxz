"""
Collection layer integration tests.

Checks that all collectors
return unified CollectedData.
"""


import json



from app.collection.file_collector import (
    FileCollector,
)


from app.collection.document_collector import (
    DocumentCollector,
)


from app.collection.telegram_collector import (
    TelegramCollector,
)


from app.collection.metadata_collector import (
    MetadataCollector,
)



from app.collection.models import (
    CollectedData,
)



def test_file_document_telegram_metadata_pipeline(
    tmp_path,
):


    # ==========================================================
    # File Collector
    # ==========================================================

    text_file = (
        tmp_path /
        "evidence.txt"
    )


    text_file.write_text(
        "Investigation data",
        encoding="utf-8",
    )


    file_result = (
        FileCollector()
        .collect(
            text_file
        )
    )


    assert isinstance(
        file_result,
        CollectedData,
    )


    assert (
        file_result.source
        ==
        "file"
    )



    # ==========================================================
    # Document Collector
    # ==========================================================

    document_result = (
        DocumentCollector()
        .collect(
            text_file
        )
    )


    assert isinstance(
        document_result,
        CollectedData,
    )


    assert (
        document_result.source
        ==
        "document"
    )



    # ==========================================================
    # Telegram Collector
    # ==========================================================

    telegram_file = (
        tmp_path /
        "result.json"
    )


    telegram_file.write_text(

        json.dumps(

            {

                "messages":

                [

                    {

                        "from":
                            "User",

                        "text":
                            "Message",

                        "date":
                            "2026-01-01",

                    }

                ]

            }

        ),

        encoding="utf-8",

    )



    telegram_result = (
        TelegramCollector()
        .collect(
            telegram_file
        )
    )


    assert isinstance(
        telegram_result,
        CollectedData,
    )


    assert (
        telegram_result.source
        ==
        "telegram"
    )



    # ==========================================================
    # Metadata Collector
    # ==========================================================

    metadata_result = (
        MetadataCollector()
        .collect(
            text_file
        )
    )


    assert isinstance(
        metadata_result,
        CollectedData,
    )


    assert (
        metadata_result.source
        ==
        "metadata"
    )


    assert (
        "sha256"
        in
        metadata_result.metadata
    )