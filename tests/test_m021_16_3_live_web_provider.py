from __future__ import annotations

import httpx
import pytest

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.live_web import LiveWebOpenWebProvider


def _query(url: str) -> OpenWebQuery:
    return OpenWebQuery(
        target_type=OsintTargetType.URL,
        value=url,
        timeout=5,
    )


def test_live_web_blocks_localhost():
    provider = LiveWebOpenWebProvider()

    result = provider.search(_query("http://127.0.0.1/"))

    assert not result.usable
    assert "not permitted" in (result.error or "").casefold()


def test_live_web_blocks_private_ipv4():
    provider = LiveWebOpenWebProvider()

    result = provider.search(_query("http://192.168.1.10/"))

    assert not result.usable
    assert "not permitted" in (result.error or "").casefold()


def test_live_web_rejects_non_http_scheme():
    provider = LiveWebOpenWebProvider()

    result = provider.search(_query("file:///etc/passwd"))

    assert not result.usable


def test_live_web_extracts_visible_html(monkeypatch):
    monkeypatch.setattr(
        LiveWebOpenWebProvider,
        "_validate_public_url",
        classmethod(lambda cls, value: None),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text=(
                "<html><head><title>Contact</title>"
                "<style>.x{display:none}</style></head>"
                "<body>Email: info@example.com "
                "Phone: +1 202 555 0100"
                "<script>secret@example.invalid</script>"
                "</body></html>"
            ),
            request=request,
        )

    provider = LiveWebOpenWebProvider(
        transport=httpx.MockTransport(handler)
    )

    result = provider.search(_query("https://example.com/contact"))

    assert result.usable
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.provider == "live_web"
    assert document.title == "Contact"
    assert "info@example.com" in (document.text or "")
    assert "+1 202 555 0100" in (document.text or "")
    assert "secret@example.invalid" not in (document.text or "")
    assert document.metadata["live_fetch"] is True


def test_live_web_is_url_only():
    provider = LiveWebOpenWebProvider()
    info = provider.info

    assert info.supported_targets == frozenset({OsintTargetType.URL})
    assert info.passive is True
    assert info.public_data_only is True
    assert info.default_enabled is True
