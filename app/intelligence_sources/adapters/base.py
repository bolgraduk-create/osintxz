from __future__ import annotations

from abc import ABC, abstractmethod

from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteSourceQuery,
)


class RemoteSourceAdapter(ABC):
    @property
    @abstractmethod
    def source_code(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[str]:
        raise NotImplementedError

    @property
    def countries(self) -> frozenset[str]:
        return frozenset()

    @property
    def global_scope(self) -> bool:
        return not self.countries

    @property
    def configured(self) -> bool:
        return True

    def supports(self, query: RemoteSourceQuery) -> bool:
        if query.capability not in self.capabilities:
            return False
        if query.country is None or self.global_scope:
            return True
        return query.country in self.countries

    @abstractmethod
    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        raise NotImplementedError
