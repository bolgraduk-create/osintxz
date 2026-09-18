from dataclasses import dataclass, replace
from uuid import UUID

from app.application.registry_persistence_service import (
    RegistryPersistenceResult,
    RegistryPersistenceService,
)
from app.intelligence_sources.policy import IntelligenceDataSanitizer
from app.registry_intelligence.contracts import (
    RegistryProviderResult,
    RegistryQuery,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySearchResult,
)
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


@dataclass(slots=True)
class RegistryEnrichmentResult:
    search: RegistrySearchResult
    persistence: RegistryPersistenceResult


class RegistryIntelligenceService:
    def __init__(
        self,
        registry: RegistryProviderRegistry | None = None,
        *,
        persistence_service: RegistryPersistenceService | None = None,
        router: RegistryQueryRouter | None = None,
        data_sanitizer: IntelligenceDataSanitizer | None = None,
    ) -> None:
        self.registry = registry or RegistryProviderRegistry()
        self.persistence_service = persistence_service
        self.router = router or RegistryQueryRouter()
        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()

    def enrich(self, query: RegistryQuery, *, case_id: UUID) -> RegistryEnrichmentResult:
        if self.persistence_service is None:
            raise RuntimeError("Registry persistence is not configured.")
        result = self.search(query)
        return RegistryEnrichmentResult(
            result,
            self.persistence_service.persist(case_id=case_id, result=result),
        )

    def search(self, query: RegistryQuery) -> RegistrySearchResult:
        out = RegistrySearchResult(query=query)
        seen: set[tuple[str, str]] = set()

        route = self.router.route(query=query, registry=self.registry)
        out.metadata["route"] = {
            "providers": list(route.provider_names),
            "blocked": [
                {
                    "provider": item.provider,
                    "access_mode": item.access_mode.value,
                    "reason": item.reason,
                }
                for item in route.blocked
            ],
            "missing_sources": list(route.missing_sources),
        }

        for provider in route.providers:
            try:
                result = provider.search(query)
                if not isinstance(result, RegistryProviderResult):
                    raise ValueError("Malformed registry provider result.")
                result = replace(
                    result,
                    provider=provider.info.name,
                    records=[
                        replace(
                            self.data_sanitizer.sanitize(record).value,
                            provider=provider.info.name,
                            source_type=provider.info.source_type,
                            trust_score=min(record.trust_score, provider.info.trust_score),
                            sensitive_legal_data=(
                                record.sensitive_legal_data
                                or provider.info.sensitive_legal_data
                            ),
                        )
                        for record in result.records[: query.limit]
                        if isinstance(record, RegistryRecord)
                    ],
                )
                result.metadata.setdefault("access_mode", provider.info.access_mode.value)
                result.metadata.setdefault("source_type", provider.info.source_type.value)
                result.metadata.setdefault("trust_score", provider.info.trust_score)
                result.metadata.setdefault(
                    "sensitive_legal_data", provider.info.sensitive_legal_data
                )
            except Exception as exc:
                result = RegistryProviderResult(
                    provider=provider.info.name,
                    status=RegistryResultStatus.FAILED,
                    error=str(exc),
                    metadata={"failure_isolated": True},
                )

            out.provider_results.append(result)
            if not result.usable:
                continue

            for record in result.records[: query.limit]:
                if record.identity_key in seen:
                    continue
                seen.add(record.identity_key)
                out.records.append(record)

        return out
