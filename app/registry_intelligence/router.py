"""M022 Registry Query Router and access-policy selection boundary."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.registry_intelligence.contracts import RegistryAccessMode, RegistryQuery
from app.registry_intelligence.provider import RegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry


@dataclass(frozen=True, slots=True)
class RegistryRouteBlock:
    provider: str
    access_mode: RegistryAccessMode
    reason: str


@dataclass(frozen=True, slots=True)
class RegistryRoute:
    query: RegistryQuery
    providers: tuple[RegistryProvider, ...] = ()
    blocked: tuple[RegistryRouteBlock, ...] = ()
    missing_sources: tuple[str, ...] = ()

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(provider.info.name for provider in self.providers)


class RegistryQueryRouter:
    """
    Select registry providers conservatively.

    This boundary intentionally does not bypass login/CAPTCHA/contract access.
    MANUAL_ASSISTED and RESTRICTED sources are visible as blocked candidates but
    never run automatically.
    """

    def route(self, *, query: RegistryQuery, registry: RegistryProviderRegistry) -> RegistryRoute:
        compatible = registry.compatible_for(query)

        requested = set(query.sources)
        missing_sources: tuple[str, ...] = ()
        if requested:
            available_names = {provider.info.name for provider in registry.all()}
            missing_sources = tuple(sorted(requested - available_names))
            compatible = tuple(
                provider for provider in compatible if provider.info.name in requested
            )

        allowed: list[RegistryProvider] = []
        blocked: list[RegistryRouteBlock] = []

        for provider in compatible:
            info = provider.info
            if info.automatic_eligible:
                allowed.append(provider)
                continue

            if info.requires_credentials:
                reason = "Provider requires credentials and is not eligible for automatic execution."
            elif info.access_mode is RegistryAccessMode.MANUAL_ASSISTED:
                reason = "Provider requires manual-assisted access."
            elif info.access_mode is RegistryAccessMode.RESTRICTED:
                reason = "Provider is restricted and cannot run automatically."
            elif not info.default_enabled:
                reason = "Provider is not enabled for automatic execution."
            else:
                reason = "Provider does not satisfy automatic access policy."

            blocked.append(
                RegistryRouteBlock(
                    provider=info.name,
                    access_mode=info.access_mode,
                    reason=reason,
                )
            )

        return RegistryRoute(
            query=query,
            providers=tuple(allowed),
            blocked=tuple(blocked),
            missing_sources=missing_sources,
        )
