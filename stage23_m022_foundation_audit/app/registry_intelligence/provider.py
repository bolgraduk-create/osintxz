from abc import ABC, abstractmethod
from app.registry_intelligence.contracts import RegistryProviderInfo, RegistryProviderResult, RegistryQuery

class RegistryProvider(ABC):
    @property
    @abstractmethod
    def info(self) -> RegistryProviderInfo:
        raise NotImplementedError

    def supports(self, query: RegistryQuery) -> bool:
        if query.domain not in self.info.domains or query.kind not in self.info.query_kinds:
            return False
        if self.info.global_scope or query.country is None:
            return True
        return query.country.strip().upper() in self.info.countries

    @abstractmethod
    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        raise NotImplementedError
