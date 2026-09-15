from hashlib import sha256

from app.infrastructure.registries.ukraine_edr_downloader import (
    UaEdrDatasetClient,
    UaEdrResource,
)


class _NoNetworkClient:
    def stream(self, *args, **kwargs):
        raise AssertionError("network must not be used for a checksum-valid cached archive")


def test_download_reuses_checksum_valid_existing_archive(tmp_path):
    payload = b"already-downloaded-official-edr-archive"
    destination = tmp_path / "generation-UO.zip"
    destination.write_bytes(payload)
    resource = UaEdrResource(
        name="UO.zip",
        resource_id="uo-test",
        url="https://data.gov.ua/dataset/example/UO.zip",
        hash_value=sha256(payload).hexdigest(),
    )

    result = UaEdrDatasetClient(client=_NoNetworkClient()).download(
        resource,
        destination,
    )

    assert result.path == destination
    assert result.size_bytes == len(payload)
    assert result.sha256 == sha256(payload).hexdigest()
