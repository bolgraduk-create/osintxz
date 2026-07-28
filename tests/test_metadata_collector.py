"""
Tests for MetadataCollector.
"""


from app.collection.metadata_collector import (
    MetadataCollector,
)



def test_metadata_collection(
    tmp_path,
):

    file = tmp_path / "evidence.txt"


    file.write_text(
        "OSINT evidence",
        encoding="utf-8",
    )


    collector = MetadataCollector()


    result = collector.collect(
        file
    )


    assert (
        result.source
        ==
        "metadata"
    )


    assert (
        result.metadata["filename"]
        ==
        "evidence.txt"
    )


    assert (
        result.metadata["extension"]
        ==
        ".txt"
    )


    assert (
        result.metadata["size"]
        >
        0
    )


    assert (
        len(
            result.metadata["sha256"]
        )
        ==
        64
    )



def test_metadata_file_missing():

    collector = MetadataCollector()


    try:

        collector.collect(
            "missing.file"
        )


        assert False


    except FileNotFoundError:

        assert True