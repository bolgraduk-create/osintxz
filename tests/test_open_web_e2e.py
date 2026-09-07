from __future__ import annotations

from uuid import uuid4

from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentService,
)
from app.models.entity import EntityType
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebDocument,
    OpenWebProviderInfo,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.extraction_bridge import (
    OpenWebIdentifierExtractionBridge,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import (
    OpenWebProviderRegistry,
)
from app.osint.open_web.service import (
    OpenWebDiscoveryService,
)
from app.services.unified_extraction_service import (
    UnifiedExtractionService,
)
from tests.golden_osint_recursive_runtime import (
    GoldenEntityService,
    GoldenEvidenceLinkService,
    GoldenEvidenceService,
    GoldenSourceService,
)


class DummyMessageRepository:
    pass


class GoldenPublicProvider(OpenWebProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def info(self) -> OpenWebProviderInfo:
        return OpenWebProviderInfo(
            name="golden_public",
            display_name="Golden Public",
            supported_targets=frozenset(
                {
                    OsintTargetType.USERNAME,
                }
            ),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=10,
        )

    def search(
        self,
        query: OpenWebQuery,
    ) -> OpenWebResult:
        self.calls += 1

        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.SUCCESS,
            documents=[
                OpenWebDocument(
                    url=(
                        "https://public.example/"
                        "profiles/golden_alice"
                    ),
                    provider=self.info.name,
                    title="Golden Alice public profile",
                    snippet=(
                        "Contact golden.alice@example.org"
                    ),
                    text=(
                        "Phone: +380501234567 "
                        "Website: https://alice.example.org"
                    ),
                    confidence=0.90,
                    reliability=0.85,
                    metadata={
                        "fixture": True,
                    },
                )
            ],
        )


def build_e2e_runtime():
    source_service = GoldenSourceService()
    evidence_service = GoldenEvidenceService()
    entity_service = GoldenEntityService()
    evidence_link_service = (
        GoldenEvidenceLinkService()
    )

    extraction_service = UnifiedExtractionService(
        session=None,
        entity_service=entity_service,
        message_repository=DummyMessageRepository(),
        evidence_service=evidence_service,
        evidence_link_service=evidence_link_service,
    )

    bridge = OpenWebIdentifierExtractionBridge(
        extraction_service
    )

    provider = GoldenPublicProvider()
    registry = OpenWebProviderRegistry()
    registry.register(provider)

    discovery_service = OpenWebDiscoveryService(
        registry
    )

    persistence_service = (
        OsintFindingPersistenceService(
            source_service=source_service,
            evidence_service=evidence_service,
            entity_service=entity_service,
            evidence_link_service=(
                evidence_link_service
            ),
        )
    )

    service = OpenWebEnrichmentService(
        discovery_service=discovery_service,
        extraction_bridge=bridge,
        persistence_service=persistence_service,
    )

    return (
        service,
        provider,
        source_service,
        evidence_service,
        entity_service,
        evidence_link_service,
    )


def test_open_web_full_offline_e2e_real_services():
    (
        service,
        provider,
        source_service,
        evidence_service,
        entity_service,
        evidence_link_service,
    ) = build_e2e_runtime()

    case_id = uuid4()

    result = service.enrich(
        OpenWebQuery(
            target_type=(
                OsintTargetType.USERNAME
            ),
            value="golden_alice",
            case_id=str(case_id),
            depth=1,
        ),
        case_id=case_id,
    )

    assert provider.calls == 1
    assert result.documents_found == 1
    assert result.findings_extracted >= 3
    assert result.persisted_findings >= 3

    entity_types = {
        entity.entity_type
        for entity
        in entity_service.repository.items
    }

    assert EntityType.EMAIL in entity_types
    assert EntityType.PHONE in entity_types
    assert EntityType.URL in entity_types

    assert source_service.repository.items
    assert evidence_service.repository.items
    assert evidence_link_service.links


def test_open_web_e2e_rerun_is_persistence_idempotent():
    (
        service,
        _provider,
        source_service,
        evidence_service,
        entity_service,
        evidence_link_service,
    ) = build_e2e_runtime()

    case_id = uuid4()
    query = OpenWebQuery(
        target_type=OsintTargetType.USERNAME,
        value="golden_alice",
        case_id=str(case_id),
    )

    first = service.enrich(
        query,
        case_id=case_id,
    )

    counts_after_first = (
        len(source_service.repository.items),
        len(evidence_service.repository.items),
        len(entity_service.repository.items),
        len(evidence_link_service.links),
    )

    second = service.enrich(
        query,
        case_id=case_id,
    )

    counts_after_second = (
        len(source_service.repository.items),
        len(evidence_service.repository.items),
        len(entity_service.repository.items),
        len(evidence_link_service.links),
    )

    assert counts_after_second == counts_after_first
    assert first.persisted_findings >= 3
    assert second.sources_created == 0
    assert second.evidences_created == 0
    assert second.entities_created == 0


def test_open_web_e2e_does_not_create_relationships():
    (
        service,
        _provider,
        _source_service,
        _evidence_service,
        _entity_service,
        _evidence_link_service,
    ) = build_e2e_runtime()

    assert not hasattr(
        service,
        "relationship_service",
    )
