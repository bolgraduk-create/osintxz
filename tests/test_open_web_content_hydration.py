from __future__ import annotations

from types import SimpleNamespace

from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)
from app.osint.open_web.contracts import (
    OpenWebDocument,
)


class ClientStub:
    def __init__(self):
        self.calls = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=(
                "alice@example.com "
                "+380501234567"
            ),
            content_type="text/html",
            http_status=200,
            metadata={
                "bounded": True,
            },
        )


def document(
    url: str,
    *,
    provider="common_crawl",
):
    return OpenWebDocument(
        url=url,
        provider=provider,
        content_type="text/html",
        metadata={
            "warc_filename": "crawl-data/x.warc.gz",
            "warc_offset": "100",
            "warc_length": "200",
        },
    )


def test_hydrator_populates_document_text():
    client = ClientStub()
    result = CommonCrawlContentHydrator(
        client,
        max_documents=3,
    ).hydrate(
        [
            document(
                "https://example.com/"
            )
        ]
    )

    assert result.hydrated == 1
    assert (
        "alice@example.com"
        in result.documents[0].text
    )
    assert (
        result.documents[0]
        .metadata[
            "content_hydration"
        ]["status"]
        == "success"
    )


def test_hydration_budget_is_bounded():
    client = ClientStub()

    result = CommonCrawlContentHydrator(
        client,
        max_documents=1,
    ).hydrate(
        [
            document(
                "https://a.example/"
            ),
            document(
                "https://b.example/"
            ),
        ]
    )

    assert result.hydrated == 1
    assert len(client.calls) == 1


def test_other_provider_is_not_hydrated():
    client = ClientStub()

    result = CommonCrawlContentHydrator(
        client
    ).hydrate(
        [
            document(
                "https://example.org/",
                provider="other",
            )
        ]
    )

    assert result.hydrated == 0
    assert result.skipped == 1
    assert client.calls == []


def test_single_document_failure_is_isolated():
    class Failing:
        def fetch(self, **kwargs):
            raise RuntimeError(
                "fixture failure"
            )

    original = document(
        "https://example.com/"
    )

    result = CommonCrawlContentHydrator(
        Failing()
    ).hydrate(
        [original]
    )

    assert result.failed == 1
    assert result.documents[0] is original
