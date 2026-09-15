from __future__ import annotations

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)
from app.registry_intelligence.countries.ukraine import (
    UA_EDR_PROVIDER_INFO,
    ukraine_source,
)
from app.registry_intelligence.providers.ukraine_edr import (
    UkraineEdrRegistryProvider,
)


class _RepositoryStub:
    pass


def test_ua_edr_does_not_advertise_tax_id() -> None:
    assert RegistryQueryKind.TAX_ID not in UA_EDR_PROVIDER_INFO.query_kinds

    descriptor = ukraine_source("ua_edr_business")
    assert descriptor is not None
    assert RegistryQueryKind.TAX_ID not in descriptor.query_kinds


def test_ua_edr_still_supports_exact_edrpou_registration_lookup() -> None:
    provider = UkraineEdrRegistryProvider(repository=_RepositoryStub())

    query = RegistryQuery(
        domain=RegistryDomain.BUSINESS,
        kind=RegistryQueryKind.REGISTRATION_ID,
        value="14359609",
        country="UA",
        sources=("ua_edr_business",),
        entity_kind=RegistryEntityKind.COMPANY,
    )

    assert provider.supports(query) is True


def test_ua_edr_rejects_tax_id_queries() -> None:
    provider = UkraineEdrRegistryProvider(repository=_RepositoryStub())

    query = RegistryQuery(
        domain=RegistryDomain.BUSINESS,
        kind=RegistryQueryKind.TAX_ID,
        value="1234567890",
        country="UA",
        sources=("ua_edr_business",),
    )

    assert provider.supports(query) is False
