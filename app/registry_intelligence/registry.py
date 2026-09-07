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

    def all(self) -> tuple[RegistryProvider, ...]:
        return tuple(sorted(self._providers.values(), key=lambda p: (p.info.priority, p.info.name)))

    def automatic_for(self, query: RegistryQuery) -> tuple[RegistryProvider, ...]:
        return tuple(p for p in self.all() if p.supports(query) and p.info.automatic_eligible)
