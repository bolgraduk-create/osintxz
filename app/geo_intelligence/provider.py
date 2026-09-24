from __future__ import annotations

from abc import ABC, abstractmethod

from app.geo_intelligence.contracts import (
    GeoEnrichmentRequest,
    GeoProviderResult,
)


class GeoIntelligenceProvider(ABC):
    @property
    @abstractmethod
    def source_code(self) -> str:
        raise NotImplementedError

    @property
    def configured(self) -> bool:
        return True

    @abstractmethod
    def enrich(self, request: GeoEnrichmentRequest) -> GeoProviderResult:
        raise NotImplementedError
