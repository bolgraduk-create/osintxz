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
from app.osint.open_web.providers.gdelt_exact_email import (
    GdeltExactEmailOpenWebProvider,
)


class _FakeLiveWeb:
    @staticmethod
    def _tls_context():
        return ssl.create_default_context()

    def search(self, query):
        if "confirmed" in query.value:
            return OpenWebResult(
                provider="live_web",
                status=OpenWebStatus.SUCCESS,
                documents=[
                    OpenWebDocument(
                        url=query.value,
                        provider="live_web",
                        title="Confirmed",
                        text=(
                            "Contact target@example.com "
                            "or call +1 312-996-7000."
                        ),
                        content_type="text/html",
                        reliability=0.85,
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
                    text="No matching address here.",
                )
            ],
        )


def _handler(request: httpx.Request):
    payload = {
        "articles": [
            {
                "url": "https://news.example/confirmed",
                "title": "Confirmed article",
                "domain": "news.example",
            },
            {
                "url": "https://news.example/false-positive",
                "title": "False positive",
                "domain": "news.example",
            },
        ]
    }

    return httpx.Response(
        200,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        request=request,
    )


def test_exact_email_provider_verifies_candidate_page():
    provider = GdeltExactEmailOpenWebProvider(
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
    document = result.documents[0]
    assert document.url == "https://news.example/confirmed"
    assert document.provider == "gdelt_exact_email"
    assert document.metadata["exact_email_verified"] is True


def test_email_boundary_match_rejects_longer_address():
    match = GdeltExactEmailOpenWebProvider._contains_exact_email

    assert match(
        "Email: target@example.com",
        "target@example.com",
    )

    assert not match(
        "Email: othertarget@example.com",
        "target@example.com",
    )


def test_provider_is_email_only():
    provider = GdeltExactEmailOpenWebProvider(
        live_web_provider=_FakeLiveWeb(),
        transport=httpx.MockTransport(_handler),
    )

    assert provider.info.supported_targets == frozenset(
        {OsintTargetType.EMAIL}
    )
    assert provider.info.automatic_eligible is True
