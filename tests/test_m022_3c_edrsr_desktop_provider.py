from __future__ import annotations

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)
from app.registry_intelligence.countries.ukraine import (
    UA_EDRSR_PROVIDER_INFO,
    ukraine_source,
)
from app.registry_intelligence.providers.remote import RemoteRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry


class _ClientStub:
    pass


def test_edrsr_is_declared_as_remote_backend_source() -> None:
    descriptor = ukraine_source("ua_edrsr")
    assert descriptor is not None
    assert descriptor.implementation_status == "implemented_remote_backend"
    assert descriptor.sensitive_legal_data is True


def test_desktop_remote_edrsr_provider_routes_exact_case_number() -> None:
    provider = RemoteRegistryProvider(
        info=UA_EDRSR_PROVIDER_INFO,
        client=_ClientStub(),
    )
    registry = RegistryProviderRegistry()
    registry.register(provider)

    query = RegistryQuery(
        domain=RegistryDomain.COURT,
        kind=RegistryQueryKind.CASE_NUMBER,
        value="761/1234/26",
        country="UA",
        sources=("ua_edrsr",),
        entity_kind=RegistryEntityKind.COURT_CASE,
    )

    assert provider.supports(query) is True
    assert registry.compatible_for(query) == (provider,)
