from app.registry_intelligence.contracts import RegistryProviderResult, RegistryQuery, RegistryRecord, RegistryResultStatus, RegistrySearchResult
from app.registry_intelligence.registry import RegistryProviderRegistry
from dataclasses import dataclass, replace
from uuid import UUID
from app.application.registry_persistence_service import RegistryPersistenceResult, RegistryPersistenceService


@dataclass(slots=True)
class RegistryEnrichmentResult:
    search: RegistrySearchResult
    persistence: RegistryPersistenceResult

class RegistryIntelligenceService:
    def __init__(self, registry: RegistryProviderRegistry | None = None, *,
                 persistence_service: RegistryPersistenceService | None = None) -> None:
        self.registry = registry or RegistryProviderRegistry()
        self.persistence_service = persistence_service

    def enrich(self, query: RegistryQuery, *, case_id: UUID) -> RegistryEnrichmentResult:
        if self.persistence_service is None:
            raise RuntimeError("Registry persistence is not configured.")
        result = self.search(query)
        return RegistryEnrichmentResult(result, self.persistence_service.persist(case_id=case_id, result=result))

    def search(self, query: RegistryQuery) -> RegistrySearchResult:
        out = RegistrySearchResult(query=query)
        seen: set[tuple[str, str]] = set()
        for provider in self.registry.automatic_for(query):
            try:
                result = provider.search(query)
                if not isinstance(result, RegistryProviderResult):
                    raise ValueError("Malformed registry provider result.")
                result = replace(result, provider=provider.info.name,
                    records=[replace(record, provider=provider.info.name)
                             for record in result.records[:query.limit] if isinstance(record, RegistryRecord)])
            except Exception as exc:
                result = RegistryProviderResult(provider=provider.info.name, status=RegistryResultStatus.FAILED, error=str(exc), metadata={"failure_isolated": True})
            out.provider_results.append(result)
            if not result.usable:
                continue
            for record in result.records[: query.limit]:
                if record.identity_key in seen:
                    continue
                seen.add(record.identity_key)
                out.records.append(record)
        return out
