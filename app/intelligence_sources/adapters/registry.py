from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import RemoteSourceQuery


class RemoteSourceAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RemoteSourceAdapter] = {}

    def register(
        self,
        adapter: RemoteSourceAdapter,
        *,
        replace: bool = False,
    ) -> None:
        key = adapter.source_code.strip().casefold()
        if key in self._adapters and not replace:
            raise ValueError(f"Remote source adapter '{key}' already registered.")
        self._adapters[key] = adapter

    def get(self, code: str) -> RemoteSourceAdapter | None:
        return self._adapters.get((code or "").strip().casefold())

    def all(self) -> tuple[RemoteSourceAdapter, ...]:
        return tuple(self._adapters[k] for k in sorted(self._adapters))

    def compatible(self, query: RemoteSourceQuery) -> tuple[RemoteSourceAdapter, ...]:
        requested = set(query.sources)
        return tuple(
            adapter
            for adapter in self.all()
            if adapter.supports(query)
            and (not requested or adapter.source_code in requested)
            and (requested or adapter.automatic_enabled)
        )
