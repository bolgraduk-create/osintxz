from __future__ import annotations

import hashlib

from app.darkweb_intelligence.discovery import DarkWebDiscoveryService
from app.darkweb_intelligence.discovery_contracts import OnionDiscoveryRequest, OnionDiscoveryStatus
from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


_STATUS_MAP = {
    OnionDiscoveryStatus.SUCCESS: RemoteAdapterStatus.SUCCESS,
    OnionDiscoveryStatus.PARTIAL: RemoteAdapterStatus.PARTIAL,
    OnionDiscoveryStatus.BLOCKED: RemoteAdapterStatus.NOT_SUPPORTED,
    OnionDiscoveryStatus.NOT_CONFIGURED: RemoteAdapterStatus.NOT_CONFIGURED,
    OnionDiscoveryStatus.FAILED: RemoteAdapterStatus.FAILED,
}


class TorOnionDiscoveryAdapter(RemoteSourceAdapter):
    def __init__(self, *, service: DarkWebDiscoveryService) -> None:
        self.service = service

    @property
    def source_code(self) -> str:
        return "tor_onion_discovery"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"darkweb_discovery", "onion_discovery"})

    @property
    def automatic_enabled(self) -> bool:
        # Crawling is always an explicit analyst action.
        return False

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Unsupported onion-discovery query.",
            )

        result = self.service.discover(
            OnionDiscoveryRequest(
                seeds=(query.value,),
                max_pages=min(query.limit, 100),
                max_depth=2,
                timeout=query.timeout,
                require_ahmia_blocklist=True,
            )
        )
        records: list[RemoteSourceRecord] = []
        for page in result.pages:
            if page.content_sha256 is None:
                continue
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=hashlib.sha256(
                        f"{page.url}|{page.content_sha256}".encode("utf-8")
                    ).hexdigest(),
                    record_type="darkweb_discovery_observation",
                    display_name=page.title or "Discovered public onion page",
                    source_url=page.url,
                    identifiers={"CONTENT_SHA256": page.content_sha256},
                    attributes={
                        "depth": page.depth,
                        "discovered_onion_urls": list(page.discovered_onion_urls),
                        "indicator_count": page.indicator_count,
                        "indicators": list(page.indicators),
                        "public_access_only": True,
                        "identity_confirmed": False,
                        "ahmia_blocklist_checked": page.metadata.get("ahmia_blocklist_checked", False),
                        "raw_body_stored": False,
                        "page_text_stored": False,
                        "raw_secret_values_stored": False,
                        **page.metadata,
                    },
                )
            )

        return RemoteAdapterResult(
            source=self.source_code,
            status=_STATUS_MAP[result.status],
            records=records,
            error="; ".join(result.errors[:5]) or None,
            metadata={
                **result.metadata,
                "blocked_onion_count": len(result.blocked_onion_urls),
                "raw_secret_values_stored": False,
                "authentication_attempted": False,
                "bypass_attempted": False,
            },
        )
