from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.open_web_enrichment_service import OpenWebEnrichmentService
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery
from app.osint.open_web.extraction_bridge import (
    OpenWebExtractionBatchResult,
    OpenWebExtractionResult,
)
from app.osint.open_web.service import OpenWebDiscoveryResponse
from app.osint.result import OsintFinding


class DiscoveryStub:
    def __init__(self, documents):
        self.documents = list(documents)
        self.calls = []

    def discover(self, query):
        self.calls.append(query)
        return OpenWebDiscoveryResponse(
            query=query,
            documents=list(self.documents),
        )


class BridgeStub:
    def __init__(self, findings):
        self.findings = list(findings)
        self.calls = []

    def extract_documents(self, documents, *, query=None):
        docs = list(documents)
        self.calls.append((docs, query))

        fallback = OpenWebDocument(
            url="",
            provider="none",
        )
        return OpenWebExtractionBatchResult(
            results=[
                OpenWebExtractionResult(
                    document=docs[0] if docs else fallback,
                    findings=list(self.findings),
                )
            ]
        )


class PersistenceStub:
    def __init__(self):
        self.calls = []

    def persist_findings(self, **kwargs):
        self.calls.append(kwargs)
        count = len(kwargs["findings"])
        return SimpleNamespace(
            persisted_findings=count,
            sources_created=1,
            evidences_created=count,
            entities_created=count,
            links_created=count,
        )


def finding(
    source,
    category="email",
    value="alice@example.com",
):
    return OsintFinding(
        category=category,
        value=value,
        source=source,
        url="https://example.test/page",
        confidence=0.8,
        reliability=0.7,
        metadata={"workflow": "open_web_discovery"},
    )


def test_full_open_web_flow_discovery_to_extraction_to_persistence():
    document = OpenWebDocument(
        url="https://example.test/page",
        provider="provider-a",
    )
    discovery = DiscoveryStub([document])
    bridge = BridgeStub([finding("provider-a")])
    persistence = PersistenceStub()

    service = OpenWebEnrichmentService(
        discovery_service=discovery,
        extraction_bridge=bridge,
        persistence_service=persistence,
    )

    query = OpenWebQuery(
        OsintTargetType.USERNAME,
        "alice",
        case_id="case-x",
    )

    result = service.enrich(
        query,
        case_id=uuid4(),
    )

    assert result.documents_found == 1
    assert result.findings_extracted == 1
    assert result.persisted_findings == 1
    assert len(discovery.calls) == 1
    assert len(bridge.calls) == 1
    assert len(persistence.calls) == 1


def test_open_web_uses_existing_open_web_discovery_goal():
    persistence = PersistenceStub()
    service = OpenWebEnrichmentService(
        discovery_service=DiscoveryStub(
            [
                OpenWebDocument(
                    url="https://e.test",
                    provider="p",
                )
            ]
        ),
        extraction_bridge=BridgeStub(
            [finding("p")]
        ),
        persistence_service=persistence,
    )

    service.enrich(
        OpenWebQuery(
            OsintTargetType.EMAIL,
            "seed@example.com",
        ),
        case_id=uuid4(),
    )

    assert (
        persistence.calls[0]["goal"]
        is DiscoveryGoal.OPEN_WEB_DISCOVERY
    )


def test_findings_group_by_provider_for_independent_provenance():
    persistence = PersistenceStub()
    service = OpenWebEnrichmentService(
        discovery_service=DiscoveryStub(
            [
                OpenWebDocument(
                    url="https://e.test",
                    provider="p",
                )
            ]
        ),
        extraction_bridge=BridgeStub(
            [
                finding("provider-b"),
                finding("provider-a"),
            ]
        ),
        persistence_service=persistence,
    )

    service.enrich(
        OpenWebQuery(
            OsintTargetType.USERNAME,
            "alice",
        ),
        case_id=uuid4(),
    )

    assert [
        call["connector"]
        for call in persistence.calls
    ] == [
        "open_web:provider-a",
        "open_web:provider-b",
    ]


def test_parent_entity_provenance_is_forwarded_without_relationship():
    persistence = PersistenceStub()
    parent = uuid4()

    service = OpenWebEnrichmentService(
        discovery_service=DiscoveryStub(
            [
                OpenWebDocument(
                    url="https://e.test",
                    provider="p",
                )
            ]
        ),
        extraction_bridge=BridgeStub(
            [finding("p")]
        ),
        persistence_service=persistence,
    )

    service.enrich(
        OpenWebQuery(
            OsintTargetType.USERNAME,
            "alice",
        ),
        case_id=uuid4(),
        parent_entity_id=parent,
    )

    assert persistence.calls[0]["parent_entity_id"] == parent
    assert not hasattr(
        service,
        "relationship_service",
    )


def test_no_findings_means_no_persistence_call():
    persistence = PersistenceStub()

    service = OpenWebEnrichmentService(
        discovery_service=DiscoveryStub([]),
        extraction_bridge=BridgeStub([]),
        persistence_service=persistence,
    )

    result = service.enrich(
        OpenWebQuery(
            OsintTargetType.PHONE,
            "+380501234567",
        ),
        case_id=uuid4(),
    )

    assert persistence.calls == []
    assert result.persisted_findings == 0


def test_service_does_not_recurse_or_commit_itself():
    assert not hasattr(
        OpenWebEnrichmentService,
        "commit",
    )
    assert not hasattr(
        OpenWebEnrichmentService,
        "enrich_recursively",
    )
