"""
Tests for FileCollector.
"""


from pathlib import Path


from app.collection.file_collector import (
    FileCollector,
)



def test_file_collection(tmp_path):

    file = tmp_path / "test.txt"


    file.write_text(
        "OSINT test data",
        encoding="utf-8",
    )


    collector = FileCollector()


    result = collector.collect(
        file
    )


    assert (
        result.source
        ==
        "file"
    )


    assert (
        result.content
        ==
        "OSINT test data"
    )


    assert (
        result.metadata["filename"]
        ==
        "test.txt"
    )



def test_file_not_found():

    collector = FileCollector()


    try:

        collector.collect(
            "missing.txt"
        )


        assert False


    except FileNotFoundError:

        assert True