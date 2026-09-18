from __future__ import annotations

import httpx

from app.darkweb_intelligence.catalog import register_darkweb_sources
from app.darkweb_intelligence.contracts import (
    DarkWebFetchStatus,
    DarkWebIndicatorKind,
)
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.darkweb_intelligence.tor_client import (
    TorConfigurationError,
    TorOnionHttpClient,
)
from app.intelligence_sources.catalog import IntelligenceSourceCatalog


ONION = "a" * 56 + ".onion"
# v3 labels are base32 a-z2-7; repeated 'a' is syntactically valid for validation tests.
URL = f"http://{ONION}/index.html"


def test_catalog_registers_darkweb_source_but_not_automatic():
    catalog = IntelligenceSourceCatalog()
    register_darkweb_sources(catalog)
    source = catalog.get("tor_public_onion_fetch")
    assert source is not None
    assert source.remote_query_supported is True
    assert source.default_enabled is False
    assert source.automatic_eligible() is False


def test_only_local_tor_proxy_is_accepted():
    TorOnionHttpClient(proxy_url="socks5h://127.0.0.1:9050")
    try:
        TorOnionHttpClient(proxy_url="socks5h://10.0.0.5:9050")
    except TorConfigurationError:
        pass
    else:
        raise AssertionError("Expected remote proxy to be blocked.")


def test_clearnet_and_v2_onion_are_blocked():
    client = TorOnionHttpClient()
    for target in (
        "https://example.com/",
        "http://abcdefghijklmnop.onion/",
    ):
        try:
            client.validate_onion_url(target)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected target to be blocked.")


def test_credentials_and_sensitive_query_parameters_are_blocked():
    client = TorOnionHttpClient()
    targets = (
        f"http://user:pass@{ONION}/",
        f"http://{ONION}/?access_token=secret",
    )
    for target in targets:
        try:
            client.validate_onion_url(target)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected credential-like URL to be blocked.")


def test_public_html_extracts_indicators_without_storing_body():
    eth = "0x" + "1" * 40
    html = f"""
    <html><head><title>Leak notice password=hunter2</title></head>
    <body>
      Contact alice@example.com or @dark_actor.
      Mirror: <a href="http://{'b'*56}.onion/path?token=abc">onion</a>
      News: <a href="https://example.org/report?tracking=1">report</a>
      Wallet: {eth}
      <script>password=do-not-index alice2@example.com</script>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == ONION
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text=html,
            request=request,
        )

    service = DarkWebIntelligenceService(
        client=TorOnionHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = service.fetch_public_onion(URL)
    assert result.status is DarkWebFetchStatus.SUCCESS
    obs = result.observation
    assert obs is not None
    assert obs.title == "Leak notice password=[REDACTED]"
    assert obs.metadata["raw_body_stored"] is False
    assert obs.metadata["page_text_stored"] is False
    values = {(item.kind, item.value) for item in obs.indicators}
    assert (DarkWebIndicatorKind.EMAIL, "alice@example.com") in values
    assert all("alice2@example.com" != item.value for item in obs.indicators)
    assert (DarkWebIndicatorKind.USERNAME, "dark_actor") in values
    assert (DarkWebIndicatorKind.ETHEREUM_ADDRESS, eth) in values
    assert (DarkWebIndicatorKind.DOMAIN, "example.org") in values
    assert any(
        item.kind is DarkWebIndicatorKind.CLEARNET_URL
        and item.value == "https://example.org/report"
        for item in obs.indicators
    )
    assert any(
        item.kind is DarkWebIndicatorKind.ONION_URL
        and "?" not in item.value
        for item in obs.indicators
    )


def test_binary_and_attachment_downloads_are_blocked():
    responses = [
        {"Content-Type": "application/zip"},
        {"Content-Type": "text/plain", "Content-Disposition": "attachment; filename=x.txt"},
    ]
    for headers in responses:
        def handler(request: httpx.Request, headers=headers) -> httpx.Response:
            return httpx.Response(200, headers=headers, content=b"x", request=request)
        service = DarkWebIntelligenceService(
            client=TorOnionHttpClient(transport=httpx.MockTransport(handler))
        )
        result = service.fetch_public_onion(URL)
        assert result.status is DarkWebFetchStatus.BLOCKED


def test_redirect_is_not_followed():
    target = f"http://{'b'*56}.onion/next"
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": target}, request=request)
    service = DarkWebIntelligenceService(
        client=TorOnionHttpClient(transport=httpx.MockTransport(handler))
    )
    result = service.fetch_public_onion(URL)
    assert calls == 1
    assert result.status is DarkWebFetchStatus.PARTIAL
    assert result.metadata["redirects_followed"] is False
    assert result.metadata["redirect_to"] == target


def test_auth_required_is_blocked_without_bypass():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)
    service = DarkWebIntelligenceService(
        client=TorOnionHttpClient(transport=httpx.MockTransport(handler))
    )
    result = service.fetch_public_onion(URL)
    assert result.status is DarkWebFetchStatus.BLOCKED
    assert result.metadata["authentication_attempted"] is False
    assert result.metadata["bypass_attempted"] is False


def test_429_is_partial_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)
    service = DarkWebIntelligenceService(
        client=TorOnionHttpClient(transport=httpx.MockTransport(handler))
    )
    result = service.fetch_public_onion(URL)
    assert result.status is DarkWebFetchStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_page_size_limit_blocks_oversized_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=b"x" * 100,
            request=request,
        )
    client = TorOnionHttpClient(transport=httpx.MockTransport(handler))
    try:
        client.fetch(URL, max_bytes=10)
    except ValueError as exc:
        assert "download limit" in str(exc)
    else:
        raise AssertionError("Expected oversized page to be blocked.")
