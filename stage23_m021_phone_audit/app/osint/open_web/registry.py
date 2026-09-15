"""Registry for Open-Web providers."""
from __future__ import annotations

from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.contracts import OpenWebQuery


class OpenWebProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, OpenWebProvider] = {}

    def register(self, provider: OpenWebProvider, *, replace: bool = False) -> None:
        name = provider.info.name.strip().casefold()
        if not name:
            raise ValueError("Open-Web provider name must not be empty.")
        if name in self._providers and not replace:
            raise ValueError(f"Open-Web provider '{name}' is already registered.")
        self._providers[name] = provider

    def get(self, name: str) -> OpenWebProvider | None:
        return self._providers.get(name.strip().casefold())

    def all(self) -> tuple[OpenWebProvider, ...]:
        return tuple(sorted(self._providers.values(), key=lambda p: (p.info.priority, p.info.name)))

    def automatic_for(self, query: OpenWebQuery) -> tuple[OpenWebProvider, ...]:
        # M021.16.5.2B credential-aware Open-Web automatic routing
        selected: list[OpenWebProvider] = []

        for provider in self.all():
            if not provider.supports(query):
                continue

            info = provider.info

            if info.automatic_eligible:
                selected.append(provider)
                continue

            if not (
                info.passive
                and info.public_data_only
                and info.default_enabled
                and info.requires_credentials
            ):
                continue

            availability = getattr(
                provider,
                "is_available",
                None,
            )

            if not callable(availability):
                continue

            try:
                available = bool(availability())
            except Exception:
                available = False

            if available:
                selected.append(provider)

        return tuple(selected)
