from __future__ import annotations

import json
import ssl

import httpx

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebDocument,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.providers.brave_exact_email import (
    BraveExactEmailOpenWebProvider,
)


class _FakeSecret:
    def get_secret_value(self):
        return "test-key"


class _FakeLiveWeb:
    @staticmethod
    def _tls_context():
        return ssl.create_default_context()

    def search(self, query):
        if "verified" in query.value:
            return OpenWebResult(
                provider="live_web",
                status=OpenWebStatus.SUCCESS,
                documents=[
                    OpenWebDocument(
                        url=query.value,
                        provider="live_web",
                        title="Verified page",
                        text="Public contact: target@example.com",
                        content_type="text/html",
                    )
                ],
            )

        return OpenWebResult(
            provider="live_web",
            status=OpenWebStatus.SUCCESS,
            documents=[
                OpenWebDocument(
                    url=query.value,
                    provider="live_web",
                    text="No exact email here.",
                )
            ],
        )


def _handler(request: httpx.Request):
    payload = {
        "query": {
            "more_results_available": False,
        },
        "web": {
            "results": [
                {
                    "url": "https://example.org/verified",
                    "title": "Verified",
                    "description": "Lead only.",
                },
                {
                    "url": "https://example.org/false-positive",
                    "title": "False positive",
                },
            ]
        },
    }

    return httpx.Response(
        200,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        request=request,
    )


def test_brave_hit_requires_live_exact_email(monkeypatch):
    import app.osint.open_web.providers.brave_exact_email as module

    monkeypatch.setattr(
        module.settings,
        "brave_search_api_key",
        _FakeSecret(),
    )

    provider = BraveExactEmailOpenWebProvider(
        live_web_provider=_FakeLiveWeb(),
        transport=httpx.MockTransport(_handler),
    )

    result = provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.EMAIL,
            value="target@example.com",
            limit=10,
            timeout=5,
        )
    )

    assert result.status is OpenWebStatus.SUCCESS
    assert len(result.documents) == 1
    assert (
        result.documents[0].url
        == "https://example.org/verified"
    )
    assert (
        result.documents[0]
        .metadata["exact_email_verified"]
        is True
    )
    assert result.metadata["exact_misses"] == 1


def test_exact_match_rejects_longer_email():
    match = (
        BraveExactEmailOpenWebProvider
        ._contains_exact_email
    )

    assert match(
        "target@example.com",
        "target@example.com",
    )
    assert not match(
        "othertarget@example.com",
        "target@example.com",
    )


def test_provider_declares_credentials():
    provider = BraveExactEmailOpenWebProvider(
        live_web_provider=_FakeLiveWeb(),
        transport=httpx.MockTransport(_handler),
    )

    assert provider.info.requires_credentials is True
    assert provider.info.default_enabled is True
