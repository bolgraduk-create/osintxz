from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.open_web_enrichment_service import OpenWebEnrichmentService
from app.application.smart_query_planner import build_smart_query_plan
from app.application.exploration_graph import ExplorationGraph, ExplorationNode
from app.application.unified_investigation_search import UnifiedSeed, UnifiedSeedKind
from app.osint.open_web.contracts import (
    OpenWebDocument,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.models import OsintTargetType


class FakeDiscovery:
    def discover(self, query):
        document = OpenWebDocument(
            url="https://example.org/profile",
            provider="test_provider",
            title="Public profile",
            snippet="contact alpha@example.org",
        )
        return SimpleNamespace(
            query=query,
            results=[
                OpenWebResult(
                    provider="test_provider",
                    status=OpenWebStatus.SUCCESS,
                    documents=[document],
                )
            ],
            documents=[document],
        )


class FakeExtraction:
    total_findings = 1

    def __init__(self):
        self.findings = [
            SimpleNamespace(
                category="email",
                value="alpha@example.org",
                source="test_provider",
                url="https://example.org/profile",
                confidence=0.9,
            )
        ]


class FakeBridge:
    def extract_documents(self, documents, *, query):
        assert len(documents) == 1
        assert query.value == "example.org"
        return FakeExtraction()


class FailingPersistence:
    def persist_findings(self, **kwargs):
        raise AssertionError("ephemeral Open Web must never persist")


def test_ephemeral_open_web_stops_before_persistence():
    service = OpenWebEnrichmentService(
        discovery_service=FakeDiscovery(),
        extraction_bridge=FakeBridge(),
        persistence_service=FailingPersistence(),
        content_hydrator=None,
    )
    query = OpenWebQuery(
        target_type=OsintTargetType.DOMAIN,
        value="example.org",
        case_id=None,
        limit=10,
        timeout=5,
        depth=1,
    )

    result = service.enrich_ephemeral(query)

    assert result.documents_found == 1
    assert result.findings_extracted == 1
    assert result.persistence == []
    assert result.persisted_findings == 0
    assert result.evidences_created == 0
    assert result.entities_created == 0


def test_persisted_enrich_reuses_ephemeral_pipeline_then_persists():
    class RecordingPersistence:
        def __init__(self):
            self.calls = 0

        def persist_findings(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                persisted_findings=1,
                sources_created=1,
                evidences_created=1,
                entities_created=1,
                links_created=1,
            )

    persistence = RecordingPersistence()
    service = OpenWebEnrichmentService(
        discovery_service=FakeDiscovery(),
        extraction_bridge=FakeBridge(),
        persistence_service=persistence,
        content_hydrator=None,
    )
    query = OpenWebQuery(
        target_type=OsintTargetType.DOMAIN,
        value="example.org",
        limit=10,
        timeout=5,
    )

    result = service.enrich(
        query,
        case_id=__import__("uuid").uuid4(),
    )

    assert persistence.calls == 1
    assert result.persisted_findings == 1
    assert result.evidences_created == 1


def test_domain_planner_now_auto_routes_open_web():
    node = ExplorationNode(
        seed=UnifiedSeed(
            kind=UnifiedSeedKind.DOMAIN,
            value="example.org",
            origin="quality_exploration",
            depth=1,
        ),
        observation_id="obs-domain",
        quality_score=90.0,
        pivot_score=92.0,
        persistence_score=80.0,
        reason="test",
        source="crtsh",
    )
    plan = build_smart_query_plan(
        ExplorationGraph(nodes=[node])
    )
    decision = plan.decisions[0]

    assert decision.action == "auto_execute"
    assert "open_web" in decision.auto_lanes
    assert "open_web" not in decision.review_lanes
    assert decision.route_hint == "classic + open web + federation"


def test_worker_uses_only_ephemeral_open_web_for_planner_lane():
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    planner_start = worker.index(
        'open_web_nodes = nodes_for_lane('
    )
    registry_start = worker.index(
        'registry_nodes = nodes_for_lane(',
        planner_start,
    )
    block = worker[planner_start:registry_start]

    assert 'lane="planner_open_web"' in block
    assert ".enrich_ephemeral(query)" in block
    assert ".enrich(" not in block
    assert "open_web_recursive_pivot_service" not in block
    assert '"plannerOpenWebExecuted"' in worker


def test_open_web_ephemeral_method_contains_no_persistence_call():
    source = Path(
        "app/application/open_web_enrichment_service.py"
    ).read_text(encoding="utf-8")

    start = source.index("    def enrich_ephemeral(")
    end = source.index("    def enrich(", start)
    block = source[start:end]

    assert "persist_findings" not in block
    assert "persistence=[]" in block
    assert "discovery_service.discover" in block
    assert "extract_documents" in block
