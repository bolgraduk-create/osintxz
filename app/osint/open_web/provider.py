"""Open-Web provider boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.osint.open_web.contracts import OpenWebProviderInfo, OpenWebQuery, OpenWebResult


class OpenWebProvider(ABC):
    """Infrastructure adapter contract for one public web/index source."""

    @property
    @abstractmethod
    def info(self) -> OpenWebProviderInfo:
        raise NotImplementedError

    def supports(self, query: OpenWebQuery) -> bool:
        return query.target_type in self.info.supported_targets

    @abstractmethod
    def search(self, query: OpenWebQuery) -> OpenWebResult:
        raise NotImplementedError
