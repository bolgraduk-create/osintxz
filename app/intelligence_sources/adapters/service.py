from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.policy import IntelligenceDataSanitizer


@dataclass(slots=True)
class RemoteFederatedSearchResult:
    query: RemoteSourceQuery
    provider_results: list[RemoteAdapterResult] = field(default_factory=list)
    records: list[RemoteSourceRecord] = field(default_factory=list)


class RemoteSourceAdapterService:
    def __init__(
        self,
        *,
        registry: RemoteSourceAdapterRegistry,
        sanitizer: IntelligenceDataSanitizer | None = None,
    ) -> None:
        self.registry = registry
        self.sanitizer = sanitizer or IntelligenceDataSanitizer()

    def search(self, query: RemoteSourceQuery) -> RemoteFederatedSearchResult:
        out = RemoteFederatedSearchResult(query=query)
        seen: set[tuple[str, str]] = set()

        for adapter in self.registry.compatible(query):
            if not adapter.configured:
                result = RemoteAdapterResult(
                    source=adapter.source_code,
                    status=RemoteAdapterStatus.NOT_CONFIGURED,
                    error="Source adapter requires configuration.",
                )
            else:
                try:
                    result = adapter.search(query)
                except Exception as exc:
                    result = RemoteAdapterResult(
                        source=adapter.source_code,
                        status=RemoteAdapterStatus.FAILED,
                        error=str(exc),
                        metadata={"failure_isolated": True},
                    )

            sanitized = self.sanitizer.sanitize(result)
            result = sanitized.value
            result.metadata = dict(result.metadata)
            if sanitized.redacted_count:
                result.metadata["secret_fields_redacted"] = (
                    int(result.metadata.get("secret_fields_redacted") or 0)
                    + sanitized.redacted_count
                )
            result.metadata["raw_secret_values_stored"] = False
            out.provider_results.append(result)

            if not result.usable:
                continue

            for record in result.records[: query.limit]:
                key = (record.source, record.record_id)
                if key in seen:
                    continue
                seen.add(key)
                out.records.append(record)

        return out
