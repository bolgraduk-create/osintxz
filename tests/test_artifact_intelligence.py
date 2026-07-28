"""
Artifact intelligence tests.
"""

from pathlib import Path

from app.services.hash_service import (
    HashService,
)

from app.services.metadata_service import (
    MetadataService,
)



def test_hash_service(tmp_path):

    file = tmp_path / "test.txt"

    file.write_text(
        "hello world"
    )


    service = HashService()


    md5 = service.calculate_md5(
        str(file)
    )

    sha256 = service.calculate_sha256(
        str(file)
    )


    size = service.calculate_file_size(
        str(file)
    )


    assert md5

    assert sha256

    assert size == 11



def test_metadata_service(tmp_path):

    file = tmp_path / "photo.jpg"

    file.write_text(
        "data"
    )


    service = MetadataService()


    metadata = service.extract_basic_metadata(
        str(file)
    )


    assert metadata["filename"] == "photo.jpg"

    assert metadata["extension"] == ".jpg"

    assert metadata["size"] == 4