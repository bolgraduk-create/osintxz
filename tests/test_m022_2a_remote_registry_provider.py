from app.infrastructure.registries.registry_api_client import RegistryApiClientError
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
)
from app.registry_intelligence.countries.ukraine import UA_EDR_PROVIDER_INFO
from app.registry_intelligence.providers.remote import RemoteRegistryProvider


class FakeClient:
    def __init__(self, *, error=None):
        self.error = error

    def search_provider(self, *, provider, query):
        if self.error:
            raise self.error
        return RegistryProviderResult(
            provider=provider,
            status=RegistryResultStatus.SUCCESS,
            metadata={"backend": True},
        )


def test_remote_provider_preserves_registry_provider_identity():
    provider = RemoteRegistryProvider(info=UA_EDR_PROVIDER_INFO, client=FakeClient())
    result = provider.search(
        RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.REGISTRATION_ID,
            "12345678",
            country="UA",
        )
    )
    assert result.provider == "ua_edr_business"
    assert result.status is RegistryResultStatus.SUCCESS
    assert result.metadata["transport"] == "registry_backend"


def test_remote_provider_isolates_backend_failure():
    provider = RemoteRegistryProvider(
        info=UA_EDR_PROVIDER_INFO,
        client=FakeClient(error=RegistryApiClientError("backend unavailable")),
    )
    result = provider.search(
        RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.REGISTRATION_ID,
            "12345678",
            country="UA",
        )
    )
    assert result.status is RegistryResultStatus.FAILED
    assert result.metadata["failure_isolated"] is True
    assert "backend unavailable" in result.error
