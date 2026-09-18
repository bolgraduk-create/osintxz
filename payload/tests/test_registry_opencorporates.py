from __future__ import annotations

import httpx

from app.infrastructure.registries.opencorporates_client import OpenCorporatesHttpClient
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.providers.opencorporates import OpenCorporatesRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


def _query(value: str, *, kind=RegistryQueryKind.NAME, country=None):
    return RegistryQuery(
        domain=RegistryDomain.BUSINESS,
        kind=kind,
        value=value,
        country=country,
    )


def test_missing_token_is_blocked_by_current_router_policy():
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token=None)
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)
    route = RegistryQueryRouter().route(query=_query("Example Ltd"), registry=registry)
    assert provider.info.requires_credentials is True
    assert route.providers == ()
    assert len(route.blocked) == 1
    assert route.blocked[0].provider == "opencorporates"


def test_configured_token_makes_provider_automatic_eligible():
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret")
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)
    route = RegistryQueryRouter().route(query=_query("Example Ltd"), registry=registry)
    assert provider.info.requires_credentials is False
    assert route.provider_names == ("opencorporates",)


def test_name_search_sends_token_country_and_maps_company():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("X-API-TOKEN")
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={"results":{"companies":[{"company":{
                "name":"Example Company Ltd",
                "company_number":"01234567",
                "jurisdiction_code":"gb",
                "company_type":"Private Limited Company",
                "current_status":"Active",
                "inactive":False,
                "registered_address_in_full":"London, UK",
                "registry_url":"https://registry.example/01234567",
                "opencorporates_url":"https://opencorporates.com/companies/gb/01234567",
                "source":{"publisher":"UK Companies House","url":"https://registry.example/","retrieved_at":"2026-09-01T00:00:00Z"}
            }}]}},
            request=request,
        )
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("Example Company", country="GB"))
    assert seen["token"] == "secret"
    assert seen["params"]["country_code"] == "gb"
    assert seen["params"]["normalise_company_name"] == "true"
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.country == "GB"
    assert record.registration_id == "01234567"
    assert record.source_type is RegistrySourceType.AGGREGATOR
    assert record.metadata["source_publisher"] == "UK Companies House"


def test_subnational_jurisdiction_maps_to_country():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results":{"companies":[{"company":{
                "name":"Example LLC",
                "company_number":"12345",
                "jurisdiction_code":"us_ga",
                "current_status":"Active"
            }}]}},
            request=request,
        )
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("Example LLC", country="US"))
    assert result.records[0].country == "US"
    assert result.records[0].jurisdiction == "us_ga"


def test_registration_id_search_uses_company_number_field_and_exact_filter():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={"results":{"companies":[
                {"company":{"name":"Wrong Candidate Ltd","company_number":"123456","jurisdiction_code":"gb"}},
                {"company":{"name":"Exact Candidate Ltd","company_number":"00123456","jurisdiction_code":"gb"}}
            ]}},
            request=request,
        )
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("00123456", kind=RegistryQueryKind.REGISTRATION_ID, country="GB"))
    assert seen["fields"] == "company_number"
    assert len(result.records) == 1
    assert result.records[0].registration_id == "00123456"
    assert result.records[0].confidence == 0.95


def test_http_429_is_partial_and_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error":"rate limited"}, request=request)
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("Example Ltd"))
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_http_401_is_failed_credentials_not_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error":"unauthorized"}, request=request)
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="bad-token", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("Example Ltd"))
    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["credentials_invalid"] is True
    assert result.metadata["retryable"] is False


def test_malformed_payload_is_failure_isolated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected":{}}, request=request)
    provider = OpenCorporatesRegistryProvider(
        client=OpenCorporatesHttpClient(api_token="secret", transport=httpx.MockTransport(handler))
    )
    result = provider.search(_query("Example Ltd"))
    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["failure_isolated"] is True
