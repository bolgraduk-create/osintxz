from __future__ import annotations

import hashlib

import httpx
import pytest

from app.darkweb_intelligence.ahmia import AhmiaDirectoryClient
from app.darkweb_intelligence.discovery import DarkWebDiscoveryService
from app.darkweb_intelligence.discovery_contracts import OnionDiscoveryRequest, OnionDiscoveryStatus
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.darkweb_intelligence.tor_client import TorOnionHttpClient
from app.exposure_intelligence.persistence import ExposurePersistenceService
from app.exposure_intelligence.service import ExposureFederationService
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord
from app.intelligence_sources.adapters.onion_discovery import TorOnionDiscoveryAdapter
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService


A = "a" * 56 + ".onion"
B = "b" * 56 + ".onion"
C = "c" * 56 + ".onion"
A_URL = f"http://{A}/"
B_URL = f"http://{B}/"
C_URL = f"http://{C}/"


def _ahmia_transport(*, blocked=()):
    hashes = "\n".join(hashlib.md5(host.encode("utf-8")).hexdigest() for host in blocked)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/blacklist/banned/":
            return httpx.Response(200, text=(hashes or "0" * 32) + "\n", request=request)
        if request.url.path == "/onions/":
            return httpx.Response(200, text=f"{A}\n{B}\n{A}\n", request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(handler)


def test_ahmia_directory_candidates_are_deduplicated_and_never_fetched_via_tor():
    client = AhmiaDirectoryClient(transport=_ahmia_transport())
    assert client.list_known_onions(limit=10) == (A_URL, B_URL)


def test_ahmia_blocklist_uses_published_md5_hostname_contract():
    client = AhmiaDirectoryClient(transport=_ahmia_transport(blocked=(A,)))
    hashes = client.blacklist_hashes()
    assert client.is_blocked(A_URL, hashes=hashes) is True
    assert client.is_blocked(B_URL, hashes=hashes) is False


def test_discovery_fails_closed_before_tor_when_required_blocklist_is_unavailable():
    tor_calls = 0

    def tor_handler(request: httpx.Request) -> httpx.Response:
        nonlocal tor_calls
        tor_calls += 1
        return httpx.Response(200, text="ok", headers={"Content-Type": "text/plain"}, request=request)

    def ahmia_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    service = DarkWebDiscoveryService(
        page_service=DarkWebIntelligenceService(client=TorOnionHttpClient(transport=httpx.MockTransport(tor_handler))),
        ahmia_client=AhmiaDirectoryClient(transport=httpx.MockTransport(ahmia_handler)),
    )
    result = service.discover(OnionDiscoveryRequest(seeds=(A_URL,), max_pages=5))
    assert result.status is OnionDiscoveryStatus.NOT_CONFIGURED
    assert result.metadata["fail_closed"] is True
    assert tor_calls == 0


def test_blocklisted_seed_is_rejected_before_tor_fetch():
    tor_calls = 0

    def tor_handler(request: httpx.Request) -> httpx.Response:
        nonlocal tor_calls
        tor_calls += 1
        return httpx.Response(200, text="should not happen", request=request)

    service = DarkWebDiscoveryService(
        page_service=DarkWebIntelligenceService(client=TorOnionHttpClient(transport=httpx.MockTransport(tor_handler))),
        ahmia_client=AhmiaDirectoryClient(transport=_ahmia_transport(blocked=(A,))),
    )
    result = service.discover(OnionDiscoveryRequest(seeds=(A_URL,), max_pages=5))
    assert result.status is OnionDiscoveryStatus.BLOCKED
    assert result.blocked_onion_urls == [A_URL]
    assert tor_calls == 0


def test_bounded_bfs_discovers_public_onion_links_without_following_clearnet():
    calls: list[str] = []

    def tor_handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        host = request.url.host
        if host == A:
            body = f'<html><title>A</title><a href="{B_URL}?token=secret">B</a><a href="https://example.org/x">web</a></html>'
        elif host == B:
            body = f'<html><title>B</title><a href="{C_URL}">C</a></html>'
        else:
            body = "<html><title>C</title>end</html>"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/html"}, request=request)

    service = DarkWebDiscoveryService(
        page_service=DarkWebIntelligenceService(client=TorOnionHttpClient(transport=httpx.MockTransport(tor_handler))),
        ahmia_client=AhmiaDirectoryClient(transport=_ahmia_transport()),
    )
    result = service.discover(
        OnionDiscoveryRequest(seeds=(A_URL,), max_pages=10, max_depth=2, per_host_limit=5)
    )
    assert result.status is OnionDiscoveryStatus.SUCCESS
    assert [page.url for page in result.pages] == [A_URL, B_URL, C_URL]
    assert result.discovered_onion_urls == [A_URL, B_URL, C_URL]
    assert all("example.org" not in url for url in result.discovered_onion_urls)
    assert all("token=" not in url for url in result.discovered_onion_urls)
    assert len(calls) == 3
    assert all(page.metadata["raw_body_stored"] is False for page in result.pages)


def test_depth_and_page_budget_stop_recursive_expansion():
    def tor_handler(request: httpx.Request) -> httpx.Response:
        next_url = B_URL if request.url.host == A else C_URL
        return httpx.Response(
            200,
            text=f'<html><a href="{next_url}">next</a></html>',
            headers={"Content-Type": "text/html"},
            request=request,
        )

    service = DarkWebDiscoveryService(
        page_service=DarkWebIntelligenceService(client=TorOnionHttpClient(transport=httpx.MockTransport(tor_handler))),
        ahmia_client=AhmiaDirectoryClient(transport=_ahmia_transport()),
    )
    result = service.discover(OnionDiscoveryRequest(seeds=(A_URL,), max_pages=1, max_depth=4))
    assert len(result.pages) == 1
    assert result.metadata["max_pages_reached"] is True


def test_adapter_maps_discovery_pages_to_metadata_only_records():
    def tor_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='<html><title>Index</title>alice@example.com</html>',
            headers={"Content-Type": "text/html"},
            request=request,
        )

    discovery = DarkWebDiscoveryService(
        page_service=DarkWebIntelligenceService(client=TorOnionHttpClient(transport=httpx.MockTransport(tor_handler))),
        ahmia_client=AhmiaDirectoryClient(transport=_ahmia_transport()),
    )
    adapter = TorOnionDiscoveryAdapter(service=discovery)
    result = adapter.search(RemoteSourceQuery(capability="darkweb_discovery", value=A_URL, limit=5))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.record_type == "darkweb_discovery_observation"
    assert record.attributes["raw_body_stored"] is False
    assert record.attributes["page_text_stored"] is False
    assert record.attributes["raw_secret_values_stored"] is False
    assert any(item["value"] == "alice@example.com" for item in record.attributes["indicators"])


def test_discovery_adapter_never_runs_in_unscoped_generic_federation():
    class ExplodingDiscovery:
        def discover(self, request):  # pragma: no cover - should never run
            raise AssertionError("generic federation must not crawl Tor")

    registry = RemoteSourceAdapterRegistry()
    registry.register(TorOnionDiscoveryAdapter(service=ExplodingDiscovery()))
    service = RemoteSourceAdapterService(registry=registry)
    result = service.search(RemoteSourceQuery(capability="darkweb_discovery", value=A_URL))
    assert result.provider_results == []
    assert result.records == []


def test_exposure_service_explicitly_routes_darkweb_discovery_and_counts_it():
    class FakeAdapter(TorOnionDiscoveryAdapter):
        def __init__(self):
            pass

        def search(self, query):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id="abc:0",
                        record_type="darkweb_discovery_observation",
                        display_name="Observation",
                        source_url=A_URL,
                        attributes={"raw_secret_values_stored": False},
                    )
                ],
            )

    registry = RemoteSourceAdapterRegistry()
    registry.register(FakeAdapter())
    exposure = ExposureFederationService(remote_service=RemoteSourceAdapterService(registry=registry))
    result = exposure.discover_onion(A_URL, limit=5)
    assert result.summary.total_records == 1
    assert result.summary.darkweb_records == 1
    assert result.summary.darkweb_discovery_records == 1
    assert result.summary.raw_secret_values_stored is False


def test_persistence_search_terms_only_include_whitelisted_non_secret_indicators():
    record = RemoteSourceRecord(
        source="tor_onion_discovery",
        record_id="x",
        record_type="darkweb_discovery_observation",
        display_name="x",
        attributes={
            "indicators": [
                {"kind": "email", "value": "alice@example.com"},
                {"kind": "domain", "value": "example.com"},
                {"kind": "password", "value": "hunter2"},
                {"kind": "access_token", "value": "secret-token"},
            ]
        },
    )
    terms = ExposurePersistenceService._safe_search_terms(record)
    assert terms == ["alice@example.com", "example.com"]
    assert "hunter2" not in terms
    assert "secret-token" not in terms


def test_discovery_request_has_hard_upper_bounds():
    with pytest.raises(ValueError):
        OnionDiscoveryRequest(seeds=(A_URL,), max_pages=101)
    with pytest.raises(ValueError):
        OnionDiscoveryRequest(seeds=(A_URL,), max_depth=5)
