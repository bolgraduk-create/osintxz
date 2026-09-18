from __future__ import annotations

import base64

import httpx

from app.infrastructure.registries.companies_house_client import (
    CompaniesHouseHttpClient,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.providers.companies_house import (
    CompaniesHouseRegistryProvider,
)
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


def _query(
    value: str,
    *,
    kind: RegistryQueryKind = RegistryQueryKind.NAME,
    country: str | None = "GB",
) -> RegistryQuery:
    return RegistryQuery(
        domain=RegistryDomain.BUSINESS,
        kind=kind,
        value=value,
        country=country,
    )


def test_missing_key_is_blocked_by_router():
    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(api_key=None)
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)

    route = RegistryQueryRouter().route(
        query=_query("OpenAI"),
        registry=registry,
    )

    assert provider.info.requires_credentials is True
    assert route.providers == ()
    assert route.blocked[0].provider == "uk_companies_house"


def test_configured_key_is_automatic_eligible():
    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(api_key="secret")
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)

    route = RegistryQueryRouter().route(
        query=_query("OpenAI"),
        registry=registry,
    )

    assert provider.info.requires_credentials is False
    assert route.provider_names == ("uk_companies_house",)


def test_exact_company_number_uses_profile_endpoint_and_basic_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={
                "company_name": "EXAMPLE LIMITED",
                "company_number": "01234567",
                "company_status": "active",
                "type": "ltd",
                "date_of_creation": "2000-01-01",
                "sic_codes": ["62012"],
                "registered_office_address": {
                    "premises": "10",
                    "address_line_1": "Example Street",
                    "locality": "London",
                    "postal_code": "SW1A 1AA",
                    "country": "United Kingdom",
                },
            },
            request=request,
        )

    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(
            api_key="secret",
            transport=httpx.MockTransport(handler),
        )
    )
    result = provider.search(
        _query(
            "01234567",
            kind=RegistryQueryKind.REGISTRATION_ID,
        )
    )

    expected = "Basic " + base64.b64encode(
        b"secret:"
    ).decode("ascii")
    assert seen["path"] == "/company/01234567"
    assert seen["auth"] == expected
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.registration_id == "01234567"
    assert record.source_type is RegistrySourceType.OFFICIAL_API
    assert record.country == "GB"
    assert record.metadata["sic_codes"] == ["62012"]


def test_missing_company_number_is_success_with_zero_records():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": "not found"},
            request=request,
        )

    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(
            api_key="secret",
            transport=httpx.MockTransport(handler),
        )
    )
    result = provider.search(
        _query(
            "99999999",
            kind=RegistryQueryKind.REGISTRATION_ID,
        )
    )

    assert result.status is RegistryResultStatus.SUCCESS
    assert result.records == []
    assert result.metadata["records_found"] == 0


def test_name_search_maps_official_search_results():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "EXAMPLE TECHNOLOGIES LTD",
                        "company_number": "SC123456",
                        "company_status": "active",
                        "company_type": "ltd",
                        "date_of_creation": "2015-06-01",
                        "address_snippet": "Edinburgh, Scotland",
                        "kind": "searchresults#company",
                    }
                ],
                "total_results": 1,
            },
            request=request,
        )

    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(
            api_key="secret",
            transport=httpx.MockTransport(handler),
        )
    )
    result = provider.search(_query("Example Technologies"))

    assert seen["q"] == "Example Technologies"
    assert seen["items_per_page"] == "20"
    assert len(result.records) == 1
    assert result.records[0].record_id == "SC123456"
    assert result.records[0].legal_address == "Edinburgh, Scotland"
    assert result.records[0].metadata["matched_by"] == "company_name_search"


def test_non_gb_country_is_not_supported():
    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(api_key="secret")
    )
    result = provider.search(
        _query("Example GmbH", country="DE")
    )

    assert result.status is RegistryResultStatus.NOT_SUPPORTED


def test_http_429_is_partial_and_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": "rate limited"},
            request=request,
        )

    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(
            api_key="secret",
            transport=httpx.MockTransport(handler),
        )
    )
    result = provider.search(_query("Example Ltd"))

    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_malformed_search_payload_is_failure_isolated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"items": "not-a-list"},
            request=request,
        )

    provider = CompaniesHouseRegistryProvider(
        client=CompaniesHouseHttpClient(
            api_key="secret",
            transport=httpx.MockTransport(handler),
        )
    )
    result = provider.search(_query("Example Ltd"))

    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["failure_isolated"] is True
