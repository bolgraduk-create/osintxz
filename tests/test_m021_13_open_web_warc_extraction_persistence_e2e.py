from __future__ import annotations

import gzip
from uuid import uuid4

import httpx

from app.application.open_web_enrichment_service import OpenWebEnrichmentService
from app.infrastructure.open_web.common_crawl_warc_client import CommonCrawlWarcContentClient
from app.models.entity import EntityType
from app.osint.finding_persistence import OsintFindingPersistenceService
from app.osint.models import OsintTargetType
from app.osint.open_web.content_hydration import CommonCrawlContentHydrator
from app.osint.open_web.contracts import OpenWebDocument, OpenWebProviderInfo, OpenWebQuery, OpenWebResult, OpenWebStatus
from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import OpenWebProviderRegistry
from app.osint.open_web.service import OpenWebDiscoveryService
from app.services.unified_extraction_service import UnifiedExtractionService
from tests.golden_osint_recursive_runtime import (
    GoldenEntityService,
    GoldenEvidenceLinkService,
    GoldenEvidenceService,
    GoldenSourceService,
)


class DummyMessageRepository:
    pass


class FixtureProvider(OpenWebProvider):
    @property
    def info(self):
        return OpenWebProviderInfo(
            name="common_crawl",
            display_name="Common Crawl Fixture",
            supported_targets=frozenset({OsintTargetType.URL}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=1,
        )

    def search(self, query):
        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.SUCCESS,
            documents=[
                OpenWebDocument(
                    url="https://fixture.example/profile",
                    provider=self.info.name,
                    content_type="text/html",
                    confidence=0.90,
                    reliability=0.90,
                    metadata={
                        "crawl_id": "CC-MAIN-2099-01",
                        "warc_filename": "crawl-data/CC-MAIN-2099-01/segments/x/warc/test.warc.gz",
                        "warc_offset": "100",
                        "warc_length": str(len(warc_payload())),
                    },
                )
            ],
        )


def warc_payload():
    html = (
        "<html><body>"
        "<p>Email: alice.m02113@example.org</p>"
        "<p>Phone: +380501234567</p>"
        "<p>Website: https://alice.example.org/contact</p>"
        "<script>hidden@example.net</script>"
        "</body></html>"
    ).encode()

    raw = (
        b"WARC/1.0\r\n"
        b"WARC-Type: response\r\n"
        b"WARC-Date: 2099-01-01T00:00:00Z\r\n"
        b"WARC-Target-URI: https://fixture.example/profile\r\n"
        b"Content-Type: application/http; msgtype=response\r\n"
        b"\r\n"
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        + html
    )
    return gzip.compress(raw)


def build_runtime():
    payload = warc_payload()

    def handler(request):
        assert request.headers.get("Range")
        return httpx.Response(206, content=payload, headers={
            "Content-Range": request.headers["Range"].replace("=", " ") + "/*"
        })

    source_service = GoldenSourceService()
    evidence_service = GoldenEvidenceService()
    entity_service = GoldenEntityService()
    evidence_link_service = GoldenEvidenceLinkService()

    extraction_service = UnifiedExtractionService(
        session=None,
        entity_service=entity_service,
        message_repository=DummyMessageRepository(),
        evidence_service=evidence_service,
        evidence_link_service=evidence_link_service,
    )

    registry = OpenWebProviderRegistry()
    registry.register(FixtureProvider())

    service = OpenWebEnrichmentService(
        discovery_service=OpenWebDiscoveryService(registry),
        extraction_bridge=OpenWebIdentifierExtractionBridge(extraction_service),
        persistence_service=OsintFindingPersistenceService(
            source_service=source_service,
            evidence_service=evidence_service,
            entity_service=entity_service,
            evidence_link_service=evidence_link_service,
        ),
        content_hydrator=CommonCrawlContentHydrator(
            CommonCrawlWarcContentClient(
                transport=httpx.MockTransport(handler),
                max_compressed_bytes=2_000_000,
                max_decompressed_bytes=4_000_000,
                max_text_chars=100_000,
            ),
            max_documents=1,
            timeout=5,
        ),
    )

    return service, source_service, evidence_service, entity_service, evidence_link_service


def test_full_warc_to_persisted_entities():
    service, sources, evidences, entities, links = build_runtime()
    case_id = uuid4()

    result = service.enrich(
        OpenWebQuery(
            OsintTargetType.URL,
            "https://fixture.example/profile",
            case_id=str(case_id),
            limit=5,
        ),
        case_id=case_id,
    )

    assert result.hydration is not None
    assert result.hydration.hydrated == 1
    assert result.hydration.failed == 0
    assert result.findings_extracted >= 3
    assert result.persisted_findings >= 3

    entity_types = {e.entity_type for e in entities.repository.items}
    assert EntityType.EMAIL in entity_types
    assert EntityType.PHONE in entity_types
    assert EntityType.URL in entity_types

    values = {
        getattr(e, "normalized_value", None) or getattr(e, "value", None)
        for e in entities.repository.items
    }
    assert any("alice.m02113@example.org" in str(v) for v in values)
    assert not any("hidden@example.net" in str(v) for v in values)

    assert sources.repository.items
    assert evidences.repository.items
    assert links.links


def test_hydration_provenance_and_lead_semantics():
    service, _, _, _, _ = build_runtime()
    case_id = uuid4()

    result = service.enrich(
        OpenWebQuery(
            OsintTargetType.URL,
            "https://fixture.example/profile",
            case_id=str(case_id),
        ),
        case_id=case_id,
    )

    meta = result.hydration.documents[0].metadata["content_hydration"]
    assert meta["status"] == "success"
    assert meta["source"] == "common_crawl_warc_range"
    assert meta["bounded"] is True

    assert result.extraction.findings
    assert all(f.metadata.get("workflow") == "open_web_discovery" for f in result.extraction.findings)
    assert all(f.metadata.get("lead_only") is True for f in result.extraction.findings)
    assert all(f.metadata.get("verified_ownership") is False for f in result.extraction.findings)


def test_full_rerun_is_idempotent():
    service, sources, evidences, entities, links = build_runtime()
    case_id = uuid4()
    query = OpenWebQuery(
        OsintTargetType.URL,
        "https://fixture.example/profile",
        case_id=str(case_id),
    )

    first = service.enrich(query, case_id=case_id)
    counts1 = (
        len(sources.repository.items),
        len(evidences.repository.items),
        len(entities.repository.items),
        len(links.links),
    )

    second = service.enrich(query, case_id=case_id)
    counts2 = (
        len(sources.repository.items),
        len(evidences.repository.items),
        len(entities.repository.items),
        len(links.links),
    )

    assert counts1 == counts2
    assert first.persisted_findings >= 3
    assert second.sources_created == 0
    assert second.evidences_created == 0
    assert second.entities_created == 0
