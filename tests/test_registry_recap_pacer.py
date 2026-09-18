from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.infrastructure.registries.recap_client import (
    CourtListenerRecapHttpClient,
    PacerPaidAccessBlockedError,
    PacerPaidFetchGuard,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.providers.recap import CourtListenerRecapRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


def _query(value: str, *, kind=RegistryQueryKind.CASE_NUMBER):
    return RegistryQuery(domain=RegistryDomain.COURT, kind=kind, value=value, country="US")


def test_without_token_router_blocks_recap_provider():
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token=None))
    registry = RegistryProviderRegistry(); registry.register(provider)
    route = RegistryQueryRouter().route(query=_query("1:23-cv-100"), registry=registry)
    assert provider.info.requires_credentials is True
    assert route.providers == ()
    assert route.blocked[0].provider == "courtlistener_recap"


def test_with_token_provider_is_automatic_eligible():
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token="token"))
    registry = RegistryProviderRegistry(); registry.register(provider)
    route = RegistryQueryRouter().route(query=_query("1:23-cv-100"), registry=registry)
    assert route.provider_names == ("courtlistener_recap",)


def test_case_number_uses_type_d_and_exact_post_filter():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"count": 2, "results": [
            {"docket_id": 100, "caseName": "Wrong v. Candidate", "docketNumber": "1:23-cv-1000", "court_id": "dcd"},
            {"docket_id": 101, "caseName": "Exact v. Candidate", "docketNumber": "Case No. 1:23-cv-100.", "court_id": "dcd", "absolute_url": "/docket/101/exact-v-candidate/", "dateFiled": "2023-02-01"},
        ]}, request=request)
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token="token", transport=httpx.MockTransport(handler)))
    result = provider.search(_query("1:23-cv-100"))
    assert seen["auth"] == "Token token"
    assert seen["params"]["type"] == "d"
    assert seen["params"]["q"] == 'docketNumber:"1:23-cv-100"'
    assert result.status is RegistryResultStatus.SUCCESS
    assert [r.display_name for r in result.records] == ["Exact v. Candidate"]
    record = result.records[0]
    assert record.entity_kind is RegistryEntityKind.COURT_CASE
    assert record.source_type is RegistrySourceType.AGGREGATOR
    assert record.metadata["pacer_recap"] is True
    assert record.metadata["paid_pacer_fetch_performed"] is False
    assert record.sensitive_legal_data is True


def test_name_search_is_docket_search_not_identity_confirmation():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"count": 1, "results": [{"docket_id": 77, "caseName": "Example LLC v. Example Corp.", "docketNumber": "2:25-cv-77", "court_id": "nysd"}]}, request=request)
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token="token", transport=httpx.MockTransport(handler)))
    result = provider.search(_query("Example LLC", kind=RegistryQueryKind.NAME))
    assert seen["type"] == "d"
    assert seen["q"] == 'caseName:"Example LLC"'
    assert result.records[0].metadata["identity_confirmed"] is False
    assert result.records[0].metadata["legal_outcome_inferred"] is False


def test_http_429_is_partial_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, request=request)
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token="token", transport=httpx.MockTransport(handler)))
    result = provider.search(_query("1:23-cv-100"))
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_non_us_query_not_supported():
    provider = CourtListenerRecapRegistryProvider(client=CourtListenerRecapHttpClient(api_token="token"))
    query = RegistryQuery(domain=RegistryDomain.COURT, kind=RegistryQueryKind.CASE_NUMBER, value="123", country="UA")
    assert provider.search(query).status is RegistryResultStatus.NOT_SUPPORTED


def test_paid_pacer_guard_blocks_without_confirmation_before_network():
    with pytest.raises(PacerPaidAccessBlockedError):
        PacerPaidFetchGuard().authorize(explicit_user_confirmation=False, authorized_budget_usd=None)


def test_paid_pacer_guard_still_blocks_even_with_explicit_budget():
    with pytest.raises(PacerPaidAccessBlockedError) as exc:
        PacerPaidFetchGuard().authorize(explicit_user_confirmation=True, authorized_budget_usd=Decimal("3.00"))
    assert "hard-blocked" in str(exc.value)
