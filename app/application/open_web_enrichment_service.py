"""M021.9 Open-Web discovery -> extraction -> persistence integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from uuid import UUID

from app.osint.capabilities import DiscoveryGoal
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
    OsintPersistenceResult,
)
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
    OpenWebHydrationBatchResult,
)
from app.osint.open_web.extraction_bridge import (
    OpenWebExtractionBatchResult,
    OpenWebIdentifierExtractionBridge,
)
from app.osint.open_web.service import (
    OpenWebDiscoveryResponse,
    OpenWebDiscoveryService,
)
from app.osint.result import OsintFinding


@dataclass(slots=True)
class OpenWebEnrichmentResult:
    query: OpenWebQuery
    discovery: OpenWebDiscoveryResponse
    hydration: OpenWebHydrationBatchResult | None
    extraction: OpenWebExtractionBatchResult
    persistence: list[OsintPersistenceResult] = field(default_factory=list)

    @property
    def documents_found(self) -> int:
        return len(self.discovery.documents)

    @property
    def findings_extracted(self) -> int:
        return self.extraction.total_findings

    @property
    def persisted_findings(self) -> int:
        return sum(item.persisted_findings for item in self.persistence)

    @property
    def sources_created(self) -> int:
        return sum(item.sources_created for item in self.persistence)

    @property
    def evidences_created(self) -> int:
        return sum(item.evidences_created for item in self.persistence)

    @property
    def entities_created(self) -> int:
        return sum(item.entities_created for item in self.persistence)

    @property
    def links_created(self) -> int:
        return sum(item.links_created for item in self.persistence)


class OpenWebEnrichmentService:
    """One non-recursive Open-Web discovery pass with existing persistence."""

    def __init__(
        self,
        *,
        discovery_service: OpenWebDiscoveryService,
        extraction_bridge: OpenWebIdentifierExtractionBridge,
        persistence_service: OsintFindingPersistenceService,
        content_hydrator: CommonCrawlContentHydrator | None = None,
    ) -> None:
        self.discovery_service = discovery_service
        self.extraction_bridge = extraction_bridge
        self.persistence_service = persistence_service
        self.content_hydrator = content_hydrator

    def enrich(
        self,
        query: OpenWebQuery,
        *,
        case_id: UUID,
        parent_entity_id: UUID | None = None,
    ) -> OpenWebEnrichmentResult:
        discovery = self.discovery_service.discover(query)

        hydration = None
        extraction_documents = list(discovery.documents)

        # M021.16.3 provider-aware hydration:
        # only Common Crawl metadata documents require WARC hydration.
        # Live Web documents already contain visible text and must go directly
        # to the unified extraction bridge.
        if self.content_hydrator is not None:
            common_crawl_documents = [
                document
                for document in discovery.documents
                if document.provider.strip().casefold() == "common_crawl"
            ]
            prehydrated_documents = [
                document
                for document in discovery.documents
                if document.provider.strip().casefold() != "common_crawl"
            ]

            if common_crawl_documents:
                hydration = self.content_hydrator.hydrate(
                    common_crawl_documents
                )
                extraction_documents = (
                    prehydrated_documents
                    + list(hydration.documents)
                )
            else:
                extraction_documents = prehydrated_documents

        extraction = self.extraction_bridge.extract_documents(
            extraction_documents,
            query=query,
        )

        by_provider: dict[str, list[OsintFinding]] = defaultdict(list)
        for finding in extraction.findings:
            provider = (
                (finding.source or "open_web").strip()
                or "open_web"
            )
            by_provider[provider].append(finding)

        persistence_results: list[OsintPersistenceResult] = []

        for provider in sorted(
            by_provider,
            key=str.casefold,
        ):
            persisted = self.persistence_service.persist_findings(
                case_id=case_id,
                target_type=query.target_type,
                target_value=query.value,
                goal=DiscoveryGoal.OPEN_WEB_DISCOVERY,
                connector=f"open_web:{provider}",
                capability_module=f"open_web_provider:{provider}",
                findings=by_provider[provider],
                parent_entity_id=parent_entity_id,
            )
            persistence_results.append(persisted)

        return OpenWebEnrichmentResult(
            query=query,
            discovery=discovery,
            hydration=hydration,
            extraction=extraction,
            persistence=persistence_results,
        )
