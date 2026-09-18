from __future__ import annotations

from app.darkweb_intelligence.contracts import DarkWebFetchStatus
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


_STATUS_MAP = {
    DarkWebFetchStatus.SUCCESS: RemoteAdapterStatus.SUCCESS,
    DarkWebFetchStatus.PARTIAL: RemoteAdapterStatus.PARTIAL,
    DarkWebFetchStatus.BLOCKED: RemoteAdapterStatus.NOT_SUPPORTED,
    DarkWebFetchStatus.NOT_CONFIGURED: RemoteAdapterStatus.NOT_CONFIGURED,
    DarkWebFetchStatus.FAILED: RemoteAdapterStatus.FAILED,
}


class TorPublicOnionAdapter(RemoteSourceAdapter):
    def __init__(self, *, service: DarkWebIntelligenceService) -> None:
        self.service = service

    @property
    def source_code(self) -> str:
        return "tor_public_onion_fetch"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"onion_url", "public_page_observation"})

    @property
    def automatic_enabled(self) -> bool:
        # Tor fetches are explicit; generic federated searches never crawl onion URLs.
        return False

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Unsupported Tor public-onion query.",
            )
        result = self.service.fetch_public_onion(query.value, timeout=query.timeout)
        records: list[RemoteSourceRecord] = []
        if result.observation is not None:
            obs = result.observation
            indicators = [
                {
                    "kind": item.kind.value,
                    "value": item.value,
                    "confidence": item.confidence,
                }
                for item in obs.indicators
            ]
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=obs.content_sha256,
                    record_type="darkweb_public_observation",
                    display_name=obs.title or "Public onion page observation",
                    source_url=obs.source_url,
                    identifiers={"CONTENT_SHA256": obs.content_sha256},
                    attributes={
                        "status_code": obs.status_code,
                        "retrieved_at": obs.retrieved_at,
                        "indicators": indicators,
                        "indicator_count": len(indicators),
                        "public_access_only": True,
                        "identity_confirmed": False,
                        "raw_body_stored": False,
                        "page_text_stored": False,
                        "raw_secret_values_stored": False,
                        **obs.metadata,
                    },
                )
            )
        return RemoteAdapterResult(
            source=self.source_code,
            status=_STATUS_MAP[result.status],
            records=records,
            error=result.error,
            metadata={
                **result.metadata,
                "raw_secret_values_stored": False,
                "authentication_attempted": False,
                "bypass_attempted": False,
            },
        )
