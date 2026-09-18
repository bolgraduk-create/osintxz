from __future__ import annotations

from app.intelligence_sources.contracts import (
    IntelligenceSourceCategory,
    IntelligenceSourceDescriptor,
)


class IntelligenceSourceCatalog:
    """
    Cross-subsystem catalog of source capabilities.

    It intentionally does not execute sources. RegistryProviderRegistry and
    app.osint.registry.ConnectorRegistry remain the execution registries.
    """

    def __init__(self) -> None:
        self._sources: dict[str, IntelligenceSourceDescriptor] = {}

    def register(
        self,
        source: IntelligenceSourceDescriptor,
        *,
        replace: bool = False,
    ) -> None:
        key = source.code
        if key in self._sources and not replace:
            raise ValueError(
                f"Intelligence source '{key}' is already registered."
            )
        self._sources[key] = source

    def unregister(self, code: str) -> None:
        self._sources.pop((code or "").strip().casefold(), None)

    def get(self, code: str) -> IntelligenceSourceDescriptor | None:
        return self._sources.get((code or "").strip().casefold())

    def all(self) -> tuple[IntelligenceSourceDescriptor, ...]:
        return tuple(
            self._sources[key]
            for key in sorted(self._sources)
        )

    def find(
        self,
        *,
        category: IntelligenceSourceCategory | None = None,
        capability: str | None = None,
        country: str | None = None,
        remote_only: bool = True,
    ) -> tuple[IntelligenceSourceDescriptor, ...]:
        items: list[IntelligenceSourceDescriptor] = []

        for source in self.all():
            if category is not None and category not in source.categories:
                continue
            if capability is not None and not source.supports_capability(
                capability
            ):
                continue
            if country is not None and not source.supports_country(country):
                continue
            if remote_only and not source.remote_query_supported:
                continue
            items.append(source)

        return tuple(items)

    def automatic_candidates(
        self,
        *,
        capability: str,
        country: str | None = None,
        credentialed_sources: frozenset[str] = frozenset(),
        verified_scope_sources: frozenset[str] = frozenset(),
    ) -> tuple[IntelligenceSourceDescriptor, ...]:
        credentialed = {
            item.strip().casefold()
            for item in credentialed_sources
        }
        verified = {
            item.strip().casefold()
            for item in verified_scope_sources
        }

        return tuple(
            source
            for source in self.find(
                capability=capability,
                country=country,
                remote_only=True,
            )
            if source.automatic_eligible(
                credentials_available=source.code in credentialed,
                verified_scope=source.code in verified,
            )
        )
