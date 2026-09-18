from __future__ import annotations

import json

import httpx

from app.infrastructure.registries.vies_client import ViesRegistryHttpClient
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
)
from app.registry_intelligence.providers.vies import ViesRegistryProvider


def _provider(payload: dict, *, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, request=request)

    client = ViesRegistryHttpClient(transport=httpx.MockTransport(handler))
    return ViesRegistryProvider(client=client)


def test_valid_prefixed_vat_creates_record():
    provider = _provider(
        {
            "countryCode": "PL",
            "vatNumber": "5213003700",
            "requestDate": "2026-09-16T12:00:00Z",
            "valid": True,
            "requestIdentifier": "REQ-1",
            "name": "Example Sp. z o.o.",
            "address": "Warsaw",
        }
    )
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="PL5213003700",
        )
    )
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    assert result.records[0].identifiers["VAT_ID"] == "PL5213003700"
    assert result.records[0].display_name == "Example Sp. z o.o."


def test_invalid_vat_is_successful_lookup_not_provider_failure():
    provider = _provider(
        {
            "countryCode": "PL",
            "vatNumber": "0000000000",
            "requestDate": "2026-09-16T12:00:00Z",
            "valid": False,
            "requestIdentifier": "",
            "name": "---",
            "address": "---",
        }
    )
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="PL0000000000",
        )
    )
    assert result.status is RegistryResultStatus.SUCCESS
    assert result.records == []
    assert result.metadata["valid"] is False


def test_greece_query_uses_el_but_stores_gr_country():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "countryCode": "EL",
                "vatNumber": "123456789",
                "requestDate": "2026-09-16T12:00:00Z",
                "valid": True,
                "requestIdentifier": "",
                "name": "---",
                "address": "---",
            },
            request=request,
        )

    provider = ViesRegistryProvider(
        client=ViesRegistryHttpClient(transport=httpx.MockTransport(handler))
    )
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="123456789",
            country="GR",
        )
    )
    assert seen["countryCode"] == "EL"
    assert seen["vatNumber"] == "123456789"
    assert result.records[0].country == "GR"
    assert result.records[0].record_id == "EL123456789"


def test_country_prefix_conflict_is_rejected_before_network_call():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500, request=request)

    provider = ViesRegistryProvider(
        client=ViesRegistryHttpClient(transport=httpx.MockTransport(handler))
    )
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="DE123456789",
            country="PL",
        )
    )
    assert result.status is RegistryResultStatus.NOT_SUPPORTED
    assert called is False


def test_transient_vies_service_error_is_partial_and_retryable():
    provider = _provider(
        {
            "actionSucceed": False,
            "errorWrappers": [
                {
                    "error": "MS_UNAVAILABLE",
                    "message": "Member State service unavailable",
                }
            ],
        }
    )
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="DE123456789",
        )
    )
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["failure_isolated"] is True


def test_http_429_is_partial_and_retryable():
    provider = _provider({"error": "rate limited"}, status_code=429)
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.VAT_ID,
            value="DE123456789",
        )
    )
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True


def test_vies_provider_only_supports_vat_id_queries():
    provider = _provider({})
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.NAME,
            value="Example GmbH",
            country="DE",
        )
    )
    assert result.status is RegistryResultStatus.NOT_SUPPORTED
