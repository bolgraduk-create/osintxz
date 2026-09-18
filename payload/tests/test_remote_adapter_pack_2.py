from __future__ import annotations

import json
import httpx

from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterStatus,
    RemoteSourceQuery,
)
from app.intelligence_sources.adapters.csl import TradeCslAdapter
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.sam_gov import SamGovEntityAdapter
from app.intelligence_sources.adapters.sec_edgar import SecEdgarAdapter
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService
from app.intelligence_sources.adapters.ted import TedSearchAdapter


def test_sec_requires_declared_user_agent():
    registry = RemoteSourceAdapterRegistry()
    registry.register(SecEdgarAdapter(user_agent=None))
    result = RemoteSourceAdapterService(registry=registry).search(
        RemoteSourceQuery("cik", "320193", sources=("us_sec_edgar",))
    )
    assert result.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_sec_exact_cik_maps_bounded_filings_and_declared_ua():
    seen = {}
    def handler(request):
        seen["path"] = request.url.path
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, json={
            "cik": 320193,
            "name": "APPLE INC",
            "sic": "3571",
            "tickers": ["AAPL"],
            "exchanges": ["Nasdaq"],
            "filings": {"recent": {
                "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
                "filingDate": ["2026-01-01", "2026-02-01"],
                "form": ["8-K", "10-Q"],
                "primaryDocument": ["a.htm", "b.htm"],
            }},
        }, request=request)
    adapter = SecEdgarAdapter(
        user_agent="OSINTXZ admin@example.com",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("cik", "320193", limit=1))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["path"].endswith("/CIK0000320193.json")
    assert seen["ua"] == "OSINTXZ admin@example.com"
    assert result.records[0].identifiers["CIK"] == "0000320193"
    assert len(result.records[0].attributes["recent_filings"]) == 1


def test_sec_invalid_cik_is_not_supported():
    result = SecEdgarAdapter(user_agent="OSINTXZ a@b.com").search(
        RemoteSourceQuery("cik", "ABC")
    )
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED


def test_ted_posts_official_expert_query_and_maps_notice():
    seen = {}
    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "totalNoticeCount": 1,
            "timedOut": False,
            "notices": [{
                "publication-number": "285496-2025",
                "notice-title": {"eng": ["Cloud services"]},
                "buyer-name": {"eng": ["Example Ministry"]},
                "notice-type": "cn-standard",
                "publication-date": "2025-05-01",
                "links": {"html": "https://ted.europa.eu/example"},
            }],
        }, request=request)
    adapter = TedSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("procurement", 'FT~"cloud"'))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["method"] == "POST"
    assert seen["path"] == "/v3/notices/search"
    assert seen["body"]["query"] == 'FT~"cloud"'
    assert seen["body"]["paginationMode"] == "PAGE_NUMBER"
    assert result.records[0].record_id == "285496-2025"
    assert result.records[0].display_name == "Cloud services"


def test_ted_rate_limit_is_partial():
    adapter = TedSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(429, request=request)
    )))
    result = adapter.search(RemoteSourceQuery("procurement", "publication-number=1-2026"))
    assert result.status is RemoteAdapterStatus.PARTIAL
    assert result.metadata["rate_limited"] is True


def test_sam_requires_api_key():
    registry = RemoteSourceAdapterRegistry()
    registry.register(SamGovEntityAdapter(api_key=None))
    result = RemoteSourceAdapterService(registry=registry).search(
        RemoteSourceQuery("company_name", "Example", sources=("us_sam_entities",))
    )
    assert result.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_sam_name_search_requests_public_sections_only():
    seen = {}
    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"entityData": [{
            "entityRegistration": {
                "ueiSAM": "RV56IG5JM6G9",
                "legalBusinessName": "EXAMPLE LLC",
                "registrationStatus": "Active",
                "cageCode": "1A2B3",
                "publicDisplayFlag": "Y",
            },
            "coreData": {"physicalAddress": {
                "city": "Washington", "stateOrProvinceCode": "DC", "countryCode": "US"
            }},
        }]}, request=request)
    adapter = SamGovEntityAdapter(
        api_key="sam-key",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("company_name", "Example"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["params"]["api_key"] == "sam-key"
    assert seen["params"]["legalBusinessName"] == "Example"
    assert seen["params"]["includeSections"] == "entityRegistration,coreData"
    assert result.records[0].attributes["cui_included"] is False


def test_sam_uei_exact_lookup():
    def handler(request):
        assert request.url.params["ueiSAM"] == "RV56IG5JM6G9"
        return httpx.Response(200, json={"entityData": [{
            "entityRegistration": {
                "ueiSAM": "RV56IG5JM6G9", "legalBusinessName": "EXAMPLE LLC"
            }, "coreData": {}
        }]}, request=request)
    adapter = SamGovEntityAdapter(
        api_key="sam-key",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("uei", "RV56IG5JM6G9"))
    assert result.records[0].identifiers["UEI"] == "RV56IG5JM6G9"


def test_csl_requires_api_key():
    registry = RemoteSourceAdapterRegistry()
    registry.register(TradeCslAdapter(api_key=None))
    result = RemoteSourceAdapterService(registry=registry).search(
        RemoteSourceQuery("name", "Example", sources=("us_trade_csl",))
    )
    assert result.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_csl_match_stays_candidate_not_identity_fact():
    seen = {}
    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"results": [{
            "id": "abc",
            "name": "EXAMPLE TRADING LTD",
            "source": "Entity List",
            "country": "GB",
            "score": 91.2,
            "addresses": ["London"],
            "source_information_url": "https://example.gov/list",
        }]}, request=request)
    adapter = TradeCslAdapter(
        api_key="trade-key",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("name", "Example Trading"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["params"]["api_key"] == "trade-key"
    record = result.records[0]
    assert record.attributes["candidate_only"] is True
    assert record.attributes["identity_confirmed"] is False
    assert record.attributes["restriction_status_inferred"] is False
    assert record.attributes["due_diligence_required"] is True
    assert record.attributes["score"] == 91.2


def test_csl_fuzzy_uses_fuzzy_name_parameter():
    def handler(request):
        assert request.url.params["fuzzy_name"] == "Exampel"
        return httpx.Response(200, json={"results": []}, request=request)
    adapter = TradeCslAdapter(
        api_key="trade-key",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("fuzzy_name", "Exampel"))
    assert result.status is RemoteAdapterStatus.SUCCESS
