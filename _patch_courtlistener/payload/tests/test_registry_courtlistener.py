from __future__ import annotations

import httpx

from app.infrastructure.registries.courtlistener_client import (
    CourtListenerHttpClient,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
)
from app.registry_intelligence.providers.courtlistener import (
    CourtListenerRegistryProvider,
)
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


def _query(value: str, *, kind=RegistryQueryKind.CASE_NUMBER):
    return RegistryQuery(
        domain=RegistryDomain.COURT,
        kind=kind,
        value=value,
        country="US",
    )


def test_without_token_current_router_blocks_provider():
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(api_token=None)
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)
    route = RegistryQueryRouter().route(
        query=_query("24-3286"), registry=registry
    )
    assert provider.info.requires_credentials is True
    assert route.providers == ()
    assert route.blocked[0].provider == "courtlistener"


def test_with_token_provider_is_automatic_eligible():
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(api_token="token")
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)
    route = RegistryQueryRouter().route(
        query=_query("24-3286"), registry=registry
    )
    assert route.provider_names == ("courtlistener",)


def test_case_number_search_uses_v4_case_law_and_token():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "count": 1,
                "results": [{
                    "absolute_url": "/opinion/123/example-v-state/",
                    "caseName": "Example v. State",
                    "caseNameFull": "Example v. State",
                    "citation": ["123 F.4th 1"],
                    "citeCount": 2,
                    "cluster_id": 123,
                    "court": "Example Court",
                    "court_id": "ca1",
                    "dateFiled": "2026-01-01",
                    "dateArgued": None,
                    "docketNumber": "24-3286",
                    "docket_id": 987,
                    "status": "Published",
                }],
            },
            request=request,
        )
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(
            api_token="token", transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("24-3286"))
    assert seen["auth"] == "Token token"
    assert seen["path"] == "/api/rest/v4/search/"
    assert seen["params"]["type"] == "o"
    assert seen["params"]["q"] == 'docketNumber:"24-3286"'
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.entity_kind is RegistryEntityKind.COURT_DECISION
    assert record.sensitive_legal_data is True
    assert record.identifiers["CASE_NUMBER"] == "24-3286"
    assert record.metadata["pacer_recap"] is False
    assert record.metadata["legal_outcome_inferred"] is False


def test_case_number_requires_exact_normalized_returned_match():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"count": 2, "results": [
            {"cluster_id": 1, "caseName": "Wrong", "docketNumber": "24-32860"},
            {"cluster_id": 2, "caseName": "Exact", "docketNumber": "No. 24–3286."},
        ]}, request=request)
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(
            api_token="token", transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("24-3286"))
    assert [r.display_name for r in result.records] == ["Exact"]


def test_name_query_is_case_name_search_not_person_identity_claim():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"count": 1, "results": [{
            "cluster_id": 3,
            "caseName": "Smith v. Jones",
            "docketNumber": "25-10",
            "status": "Published",
        }]}, request=request)
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(
            api_token="token", transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("Smith v. Jones", kind=RegistryQueryKind.NAME))
    assert seen["q"] == 'caseName:"Smith v. Jones"'
    assert result.records[0].metadata["identity_confirmed"] is False


def test_http_429_is_partial_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, request=request)
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(
            api_token="token", transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("24-3286"))
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_http_401_is_failed_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={}, request=request)
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(
            api_token="bad", transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("24-3286"))
    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["credentials_invalid"] is True
    assert result.metadata["retryable"] is False


def test_non_us_query_is_not_supported():
    provider = CourtListenerRegistryProvider(
        client=CourtListenerHttpClient(api_token="token")
    )
    query = RegistryQuery(
        domain=RegistryDomain.COURT,
        kind=RegistryQueryKind.CASE_NUMBER,
        value="123",
        country="UA",
    )
    result = provider.search(query)
    assert result.status is RegistryResultStatus.NOT_SUPPORTED
