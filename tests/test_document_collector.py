"""
Tests for DocumentCollector.
"""


from app.collection.document_collector import (
    DocumentCollector,
)



def test_txt_document_collection(
    tmp_path,
):

    file = tmp_path / "report.txt"


    file.write_text(
        "Investigation document",
        encoding="utf-8",
    )


    collector = DocumentCollector()


    result = collector.collect(
        file
    )


    assert (
        result.source
        ==
        "document"
    )


    assert (
        result.content
        ==
        "Investigation document"
    )


    assert (
        result.metadata["extension"]
        ==
        ".txt"
    )



def test_unsupported_document(
    tmp_path,
):

    file = tmp_path / "test.exe"


    file.write_text(
        "binary",
        encoding="utf-8",
    )


    collector = DocumentCollector()


    try:

        collector.collect(
            file
        )

        assert False


    except ValueError:

        assert True