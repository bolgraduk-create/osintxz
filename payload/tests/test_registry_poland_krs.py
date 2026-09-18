from __future__ import annotations

import httpx

from app.infrastructure.registries.poland_krs_client import PolandKrsHttpClient
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.providers.poland_krs import (
    PolandKrsRegistryProvider,
)
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


def _query(value: str, *, country: str | None = "PL") -> RegistryQuery:
    return RegistryQuery(
        domain=RegistryDomain.BUSINESS,
        kind=RegistryQueryKind.REGISTRATION_ID,
        value=value,
        country=country,
    )


def _payload(krs: str = "0000019411") -> dict:
    return {
        "odpis": {
            "naglowekP": {"numerKRS": krs},
            "dane": {
                "dzial1": {
                    "danePodmiotu": {
                        "nazwa": "ALLEGRO SPÓŁKA AKCYJNA",
                        "nazwaSkrocona": "ALLEGRO S.A.",
                        "formaPrawna": "SPÓŁKA AKCYJNA",
                        "identyfikatory": {
                            "krs": krs,
                            "nip": "5252674798",
                            "regon": "365331553",
                        },
                    },
                    "siedzibaIAdres": {
                        "siedziba": {
                            "miejscowosc": "POZNAŃ",
                            "wojewodztwo": "WIELKOPOLSKIE",
                        },
                        "adres": {
                            "ulica": "UL. PRZYKŁADOWA",
                            "nrDomu": "1",
                            "miejscowosc": "POZNAŃ",
                            "kodPocztowy": "60-001",
                            "kraj": "POLSKA",
                        },
                    },
                    "dataRejestracji": "2001-01-01",
                }
            },
        }
    }


def test_provider_is_automatic_without_credentials():
    provider = PolandKrsRegistryProvider(client=PolandKrsHttpClient())
    registry = RegistryProviderRegistry()
    registry.register(provider)
    route = RegistryQueryRouter().route(
        query=_query("19411"),
        registry=registry,
    )
    assert provider.info.requires_credentials is False
    assert route.provider_names == ("pl_krs",)


def test_short_krs_number_is_zero_padded_and_p_register_used_first():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["register"] = request.url.params["rejestr"]
        return httpx.Response(200, json=_payload(), request=request)

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("19411"))

    assert seen["path"].endswith("/OdpisAktualny/0000019411")
    assert seen["register"] == "P"
    assert result.status is RegistryResultStatus.SUCCESS
    assert result.records[0].registration_id == "0000019411"
    assert result.records[0].source_type is RegistrySourceType.OFFICIAL_OPEN_DATA
    assert result.records[0].identifiers["NIP"] == "5252674798"


def test_404_in_p_falls_back_to_s():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        register = request.url.params["rejestr"]
        calls.append(register)
        if register == "P":
            return httpx.Response(404, json={}, request=request)
        return httpx.Response(
            200,
            json=_payload("0000006865"),
            request=request,
        )

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("6865"))

    assert calls == ["P", "S"]
    assert result.status is RegistryResultStatus.SUCCESS
    assert result.metadata["register"] == "S"
    assert result.records[0].jurisdiction == "PL-KRS-S"


def test_404_in_both_registers_is_success_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={}, request=request)

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("9999999999"))

    assert result.status is RegistryResultStatus.SUCCESS
    assert result.records == []
    assert result.metadata["registers_checked"] == ["P", "S"]


def test_invalid_krs_is_not_supported_without_network():
    called = False
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500, request=request)

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("ABC"))
    assert result.status is RegistryResultStatus.NOT_SUPPORTED
    assert called is False


def test_wrong_country_is_not_supported():
    provider = PolandKrsRegistryProvider(client=PolandKrsHttpClient())
    result = provider.search(_query("19411", country="DE"))
    assert result.status is RegistryResultStatus.NOT_SUPPORTED


def test_429_is_partial_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, request=request)

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("19411"))
    assert result.status is RegistryResultStatus.PARTIAL
    assert result.metadata["retryable"] is True
    assert result.metadata["rate_limited"] is True


def test_malformed_payload_is_failed_and_isolated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"unexpected": True},
            request=request,
        )

    provider = PolandKrsRegistryProvider(
        client=PolandKrsHttpClient(
            transport=httpx.MockTransport(handler)
        )
    )
    result = provider.search(_query("19411"))
    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["failure_isolated"] is True
