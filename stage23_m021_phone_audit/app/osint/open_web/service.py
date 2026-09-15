"""M021.7 Open-Web Discovery orchestration boundary.

No concrete network provider is registered here. The service only executes
explicitly registered, policy-eligible providers and isolates failures.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.osint.open_web.contracts import (
    OpenWebDocument, OpenWebQuery, OpenWebResult, OpenWebStatus,
)
from app.osint.open_web.registry import OpenWebProviderRegistry


@dataclass(slots=True)
class OpenWebDiscoveryResponse:
    query: OpenWebQuery
    results: list[OpenWebResult] = field(default_factory=list)
    documents: list[OpenWebDocument] = field(default_factory=list)

    @property
    def provider_count(self) -> int:
        return len(self.results)


class OpenWebDiscoveryService:
    def __init__(self, registry: OpenWebProviderRegistry | None = None) -> None:
        self.registry = registry or OpenWebProviderRegistry()

    def discover(self, query: OpenWebQuery) -> OpenWebDiscoveryResponse:
        response = OpenWebDiscoveryResponse(query=query)
        seen: set[tuple[str, str]] = set()

        for provider in self.registry.automatic_for(query):
            try:
                result = provider.search(query)
            except Exception as exc:
                result = OpenWebResult(
                    provider=provider.info.name,
                    status=OpenWebStatus.FAILED,
                    error=str(exc),
                    metadata={"failure_isolated": True},
                )


            # M021.16.7.10 RATE LIMIT IS NOT PROVIDER FAILURE
            #
            # HTTP 429 means the public upstream temporarily throttled us.
            # The provider itself is operational; represent this as PARTIAL
            # instead of FAILED so UI/diagnostics do not report a broken
            # connector. No bypass, proxy rotation or evasion is attempted.
            if (
                result.status is OpenWebStatus.FAILED
                and result.error
                and (
                    "429 Too Many Requests" in result.error
                    or "HTTP 429" in result.error
                )
            ):
                metadata = dict(result.metadata)
                metadata.update(
                    {
                        "rate_limited": True,
                        "retryable": True,
                        "failure_isolated": True,
                    }
                )
                result = OpenWebResult(
                    provider=result.provider,
                    status=OpenWebStatus.PARTIAL,
                    documents=list(result.documents),
                    error=(
                        "Public upstream rate limit reached (HTTP 429). "
                        "Retry later."
                    ),
                    metadata=metadata,
                )

            if result.provider.strip().casefold() != provider.info.name.strip().casefold():
                result.metadata.setdefault("reported_provider", result.provider)
                result.provider = provider.info.name

            response.results.append(result)
            if not result.usable:
                continue

            for document in result.documents[: query.limit]:
                if not document.url.strip():
                    continue
                key = document.identity_key
                if key in seen:
                    continue
                seen.add(key)
                response.documents.append(document)

        return response
