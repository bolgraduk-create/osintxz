"""M022 Registry Query Router and access-policy selection boundary."""
from __future__ import annotations

from dataclasses import dataclass

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
    """Select registry providers conservatively.

    Automatic routing keeps the original strict policy: only providers whose
    metadata declares them automatically eligible are executed.

    Explicit source selection is intentionally a little more permissive so the
    desktop can use configured API-backed registries such as Companies House or
    CourtListener. It still never bypasses access controls: MANUAL_ASSISTED and
    RESTRICTED providers remain blocked, providers still requiring credentials
    remain blocked, and non-public sources are not executed by this boundary.
    """

    _AUTOMATABLE_ACCESS = {
        RegistryAccessMode.API,
        RegistryAccessMode.PUBLIC_AUTOMATED,
    }

    def route(
        self,
        *,
        query: RegistryQuery,
        registry: RegistryProviderRegistry,
    ) -> RegistryRoute:
        compatible = registry.compatible_for(query)

        requested = set(query.sources)
        explicit = bool(requested)
        missing_sources: tuple[str, ...] = ()
        if explicit:
            available_names = {provider.info.name for provider in registry.all()}
            missing_sources = tuple(sorted(requested - available_names))
            compatible = tuple(
                provider
                for provider in compatible
                if provider.info.name in requested
            )

        allowed: list[RegistryProvider] = []
        blocked: list[RegistryRouteBlock] = []

        for provider in compatible:
            info = provider.info

            if explicit:
                reason = self._explicit_block_reason(info)
                if reason is None:
                    allowed.append(provider)
                else:
                    blocked.append(
                        RegistryRouteBlock(
                            provider=info.name,
                            access_mode=info.access_mode,
                            reason=reason,
                        )
                    )
                continue

            if info.automatic_eligible:
                allowed.append(provider)
                continue

            blocked.append(
                RegistryRouteBlock(
                    provider=info.name,
                    access_mode=info.access_mode,
                    reason=self._automatic_block_reason(info),
                )
            )

        return RegistryRoute(
            query=query,
            providers=tuple(allowed),
            blocked=tuple(blocked),
            missing_sources=missing_sources,
        )

    def _explicit_block_reason(self, info) -> str | None:
        if info.access_mode is RegistryAccessMode.MANUAL_ASSISTED:
            return "Provider requires manual-assisted access."
        if info.access_mode is RegistryAccessMode.RESTRICTED:
            return "Provider is restricted and cannot run automatically."
        if info.access_mode not in self._AUTOMATABLE_ACCESS:
            return "Provider access mode is not executable by the automatic registry client."
        if not info.public_data_only:
            return "Provider is not declared public-data-only."
        if info.requires_credentials:
            return "Provider requires credentials that are not configured."
        return None

    @staticmethod
    def _automatic_block_reason(info) -> str:
        if info.requires_credentials:
            return "Provider requires credentials and is not eligible for automatic execution."
        if info.access_mode is RegistryAccessMode.MANUAL_ASSISTED:
            return "Provider requires manual-assisted access."
        if info.access_mode is RegistryAccessMode.RESTRICTED:
            return "Provider is restricted and cannot run automatically."
        if not info.default_enabled:
            return "Provider is not enabled for automatic execution."
        return "Provider does not satisfy automatic access policy."
