from app.registry_intelligence.contracts import RegistryQuery
from app.registry_intelligence.provider import RegistryProvider


class RegistryProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, RegistryProvider] = {}

    def register(self, provider: RegistryProvider, *, replace: bool = False) -> None:
        key = provider.info.name.strip().casefold()
        if not key:
            raise ValueError("Registry provider name must not be empty.")
        if key in self._providers and not replace:
            raise ValueError(f"Registry provider '{key}' already registered.")
        self._providers[key] = provider

    def get(self, name: str) -> RegistryProvider | None:
        return self._providers.get((name or "").strip().casefold())

    def all(self) -> tuple[RegistryProvider, ...]:
        return tuple(
            sorted(
                self._providers.values(),
                key=lambda provider: (provider.info.priority, provider.info.name),
            )
        )

    def compatible_for(self, query: RegistryQuery) -> tuple[RegistryProvider, ...]:
        return tuple(provider for provider in self.all() if provider.supports(query))

    def automatic_for(self, query: RegistryQuery) -> tuple[RegistryProvider, ...]:
        providers = self.compatible_for(query)
        if query.sources:
            requested = set(query.sources)
            providers = tuple(provider for provider in providers if provider.info.name in requested)
        return tuple(provider for provider in providers if provider.info.automatic_eligible)
