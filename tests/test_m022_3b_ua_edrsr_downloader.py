from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from app.infrastructure.registries.ukraine_edrsr_downloader import (
    UaEdrsrDatasetClient,
    UaEdrsrResource,
)


def test_resolve_year_selects_official_yearly_zip_and_refreshes_checksum():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/3/action/package_search"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "results": [
                            {
                                "id": "dataset-2026",
                                "name": "ediniy-derzhavniy-reestr-sudovih-rishen-za-2026-rik_7636",
                                "title": "Єдиний державний реєстр судових рішень за 2026 рік.",
                                "state": "active",
                                "metadata_modified": "2026-09-13T06:17:00+03:00",
                                "organization": {
                                    "id": "b5ee25dd-1516-4a2a-a9cb-7afb5e8ec61a",
                                    "title": "Державна судова адміністрація України",
                                },
                                "resources": [
                                    {
                                        "id": "zip-resource",
                                        "name": "edrsr_data_2026.zip",
                                        "format": "ZIP",
                                        "url": "https://data.gov.ua/dataset/x/resource/y/download/edrsr_data_2026.zip",
                                        "last_modified": "2026-09-13T06:15:00+03:00",
                                        "hash": None,
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        if request.url.path.endswith("/api/3/action/resource_show"):
            assert request.url.params["id"] == "zip-resource"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "zip-resource",
                        "name": "edrsr_data_2026.zip",
                        "format": "ZIP",
                        "url": "https://data.gov.ua/dataset/x/resource/y/download/edrsr_data_2026.zip",
                        "last_modified": "2026-09-13T06:15:00+03:00",
                        "hash": "12dc69e4fac79392021714bc1d7857c5",
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolved = UaEdrsrDatasetClient(client).resolve_year(2026)
    assert resolved.dataset_year == 2026
    assert resolved.dataset_id == "dataset-2026"
    assert resolved.resource.resource_id == "zip-resource"
    assert resolved.resource.name == "edrsr_data_2026.zip"
    assert resolved.resource.hash_value == "12dc69e4fac79392021714bc1d7857c5"
    assert len(resolved.fingerprint) == 32


def test_cached_archive_is_reused_only_when_official_checksum_matches(tmp_path: Path):
    payload = b"official-edrsr-test"
    destination = tmp_path / "edrsr_data_2026.zip"
    destination.write_bytes(payload)
    resource = UaEdrsrResource(
        name=destination.name,
        resource_id="r1",
        url="https://data.gov.ua/example/edrsr_data_2026.zip",
        hash_value=hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    )

    def must_not_download(request: httpx.Request) -> httpx.Response:
        raise AssertionError("validated cache must avoid a network download")

    client = UaEdrsrDatasetClient(
        httpx.Client(transport=httpx.MockTransport(must_not_download))
    )
    downloaded = client.download(resource, destination)
    assert downloaded.path == destination
    assert downloaded.size_bytes == len(payload)
    assert downloaded.sha256 == hashlib.sha256(payload).hexdigest()


def test_non_official_resource_url_is_rejected():
    resource = UaEdrsrResource(
        name="edrsr_data_2026.zip",
        resource_id="r1",
        url="https://example.com/edrsr_data_2026.zip",
    )
    try:
        UaEdrsrDatasetClient().download(resource, Path("ignored.zip"))
    except ValueError as exc:
        assert "official HTTPS data.gov.ua" in str(exc)
    else:
        raise AssertionError("non-official EDRSR URLs must fail closed")
