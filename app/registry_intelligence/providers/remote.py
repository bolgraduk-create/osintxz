"""Remote registry-provider adapter used by the desktop application."""
from __future__ import annotations

from app.infrastructure.registries.registry_api_client import (
    RegistryApiClientError,
    RegistryApiHttpClient,
)
from app.registry_intelligence.contracts import (
    RegistryProviderInfo,
    RegistryProviderResult,
    RegistryQuery,
    RegistryResultStatus,
)
from app.registry_intelligence.provider import RegistryProvider


class RemoteRegistryProvider(RegistryProvider):
    def __init__(
        self,
        *,
        info: RegistryProviderInfo,
        client: RegistryApiHttpClient,
    ) -> None:
        self._info = info
        self.client = client

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Query is not supported by this remote registry provider.",
                metadata={"transport": "registry_backend"},
            )

        try:
            result = self.client.search_provider(
                provider=self.info.name,
                query=query,
            )
        except RegistryApiClientError as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={
                    "transport": "registry_backend",
                    "failure_isolated": True,
                },
            )

        result.metadata.setdefault("transport", "registry_backend")
        return result
