import json

import httpx
import pytest

from app.infrastructure.registries.registry_api_client import (
    RegistryApiClientError,
    RegistryApiHttpClient,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
)
from app.registry_intelligence.transport import registry_provider_result_to_wire


def query():
    return RegistryQuery(
        RegistryDomain.BUSINESS,
        RegistryQueryKind.REGISTRATION_ID,
        "12345678",
        country="UA",
        sources=("ua_edr_business",),
        entity_kind=RegistryEntityKind.COMPANY,
    )


def test_registry_api_client_posts_bounded_query_and_parses_result():
    result = RegistryProviderResult(
        provider="ua_edr_business",
        status=RegistryResultStatus.SUCCESS,
        records=[
            RegistryRecord(
                provider="ua_edr_business",
                domain=RegistryDomain.BUSINESS,
                record_id="company:101",
                display_name="TEST COMPANY",
                country="UA",
                registration_id="12345678",
                entity_kind=RegistryEntityKind.COMPANY,
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/providers/ua_edr_business/search"
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content.decode("utf-8"))
        assert body["limit"] == 20
        assert body["country"] == "UA"
        return httpx.Response(200, json=registry_provider_result_to_wire(result))

    client = RegistryApiHttpClient(
        base_url="http://127.0.0.1:8011",
        token="secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        response = client.search_provider(provider="ua_edr_business", query=query())
    finally:
        client.close()

    assert response.status is RegistryResultStatus.SUCCESS
    assert response.records[0].display_name == "TEST COMPANY"


def test_registry_api_client_rejects_plain_http_for_remote_hosts():
    with pytest.raises(ValueError, match="HTTPS"):
        RegistryApiHttpClient(base_url="http://registry.example.com")


def test_registry_api_client_does_not_accept_cross_provider_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "provider": "different_provider",
                "status": "success",
                "records": [],
                "error": None,
                "metadata": {},
            },
        )

    client = RegistryApiHttpClient(
        base_url="http://localhost:8011",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(RegistryApiClientError, match="different provider"):
            client.search_provider(provider="ua_edr_business", query=query())
    finally:
        client.close()
