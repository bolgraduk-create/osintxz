from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.exploration_graph import (
    ExplorationGraph,
    ExplorationNode,
    build_exploration_graph,
)
from app.application.search_quality_benchmark import (
    load_benchmark_fixture,
    run_search_quality_benchmark,
)
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
)
from app.interface.desktop.workers.unified_investigation_search_worker import (
    UnifiedInvestigationSearchWorker,
)
from app.osint.result import OsintFinding, OsintResult, ResultStatus


def _quality_url_row(
    *,
    url: str = "https://gitlab.com/torvalds/linux",
    seed: str = "https://gitlab.com/torvalds",
    depth: int = 0,
    explore: bool = True,
) -> dict:
    return {
        "lane": "Open-Web",
        "source": "Common Crawl",
        "title": url,
        "detail": "Historical URL",
        "type": "url",
        "url": url,
        "seed": seed,
        "seedType": "url",
        "depth": depth,
        "identifiers": {"url": url},
        "qualityObservationId": "obs-url-1",
        "qualityScore": 88.0,
        "qualityPivotScore": 91.0,
        "qualityPersistenceScore": 79.0,
        "qualityWouldExplore": explore,
        "qualityWouldPersist": False,
    }


def test_quality_url_descendant_becomes_ephemeral_seed_without_persistence():
    initial = UnifiedSeed(
        UnifiedSeedKind.URL,
        "https://gitlab.com/torvalds",
    )

    graph = build_exploration_graph(
        [_quality_url_row()],
        initial_seeds=[initial],
        max_nodes=8,
        max_depth=2,
    )

    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    assert node.seed.kind is UnifiedSeedKind.URL
    assert node.seed.value == "https://gitlab.com/torvalds/linux"
    assert node.seed.origin == "quality_exploration"
    assert node.seed.metadata["ephemeral"] is True
    assert node.persistence_score == 79.0
    assert node.pivot_score == 91.0


def test_verified_account_can_explore_profile_url_without_repeating_username():
    initial = UnifiedSeed(UnifiedSeedKind.USERNAME, "wixxlexx")
    row = {
        "lane": "Classic OSINT",
        "source": "Maigret",
        "title": "wixxlexx",
        "detail": "Account",
        "type": "account",
        "url": "https://github.com/wixxlexx",
        "seed": "wixxlexx",
        "seedType": "username",
        "depth": 0,
        "identifiers": {"username": "wixxlexx"},
        "accountVerificationStatus": "verified",
        "qualityObservationId": "obs-account-1",
        "qualityScore": 96.0,
        "qualityPivotScore": 95.0,
        "qualityPersistenceScore": 94.0,
        "qualityWouldExplore": True,
        "qualityWouldPersist": True,
    }

    graph = build_exploration_graph(
        [row],
        initial_seeds=[initial],
        max_nodes=8,
        max_depth=2,
    )

    assert [node.seed.kind for node in graph.nodes] == [
        UnifiedSeedKind.URL
    ]
    assert graph.nodes[0].seed.value == "https://github.com/wixxlexx"
    assert graph.skipped_initial >= 1


def test_non_approved_quality_row_never_enters_exploration_graph():
    graph = build_exploration_graph(
        [_quality_url_row(explore=False)],
        max_nodes=8,
        max_depth=2,
    )

    assert graph.nodes == []
    assert graph.skipped_not_approved == 1


def test_exploration_graph_respects_depth_limit():
    graph = build_exploration_graph(
        [_quality_url_row(depth=2)],
        max_nodes=8,
        max_depth=2,
    )

    assert graph.nodes == []
    assert graph.skipped_depth == 1


def test_existing_pivot_is_not_scheduled_again():
    discovered = UnifiedSeed(
        UnifiedSeedKind.URL,
        "https://gitlab.com/torvalds/linux",
        origin="remote",
        depth=1,
    )

    graph = build_exploration_graph(
        [_quality_url_row()],
        existing_seeds=[discovered],
        max_nodes=8,
        max_depth=2,
    )

    assert graph.nodes == []
    assert graph.skipped_initial >= 1


def test_r13_26b_url_benchmark_row_builds_exploration_node():
    fixture = load_benchmark_fixture(
        Path(__file__).parent
        / "fixtures"
        / "search_quality_benchmark"
        / "scenarios.json"
    )
    report = run_search_quality_benchmark(fixture)
    scenario = next(
        item
        for item in report.scenarios
        if item.name == "url_scope_and_pivots"
    )
    row = next(
        item
        for item in scenario.rows
        if item["_benchmarkId"] == "url-descendant"
    )

    graph = build_exploration_graph(
        [row],
        initial_seeds=[
            UnifiedSeed(
                UnifiedSeedKind.URL,
                "https://gitlab.com/torvalds",
            )
        ],
    )

    assert row["qualityWouldExplore"] is True
    assert row["qualityWouldPersist"] is False
    assert len(graph.nodes) == 1
    assert graph.nodes[0].seed.value.endswith("/linux")


class _FakeExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute_defaults(self, **kwargs):
        self.calls.append(dict(kwargs))
        finding = OsintFinding(
            category="domain",
            value="example.org",
            confidence=0.92,
            reliability=0.90,
            source="example",
            url="https://example.org",
            metadata={"public_data_only": True},
        )
        result = OsintResult(
            connector="FakeExplorer",
            status=ResultStatus.SUCCESS,
            findings=[finding],
        )
        record = SimpleNamespace(
            result=result,
            runtime_connector_name="FakeExplorer",
        )
        route = SimpleNamespace(
            goal=SimpleNamespace(value="historical_web")
        )
        execution = SimpleNamespace(
            route=route,
            status=SimpleNamespace(value="success"),
            records=[record],
        )
        return (execution,)


def test_worker_exploration_uses_execution_boundary_without_case_persistence():
    seed = UnifiedSeed(
        UnifiedSeedKind.URL,
        "https://example.org/profile",
        origin="quality_exploration",
        depth=1,
        parent_ref="obs-1",
        metadata={"ephemeral": True},
    )
    graph = ExplorationGraph(
        nodes=[
            ExplorationNode(
                seed=seed,
                observation_id="obs-1",
                quality_score=90.0,
                pivot_score=92.0,
                persistence_score=70.0,
                reason="Quality-approved source/profile URL",
                source="test",
                parent_seed_kind="username",
                parent_seed_value="alice",
            )
        ]
    )
    execution_service = _FakeExecutionService()
    container = SimpleNamespace(
        osint_enrichment_service=SimpleNamespace(
            execution_service=execution_service
        )
    )
    worker = UnifiedInvestigationSearchWorker(
        case_id="00000000-0000-0000-0000-000000000001",
        profile={},
    )
    rows: list[dict] = []
    providers: list[dict] = []
    errors: list[dict] = []

    executed = worker._run_ephemeral_exploration(
        container=container,
        graph=graph,
        results=rows,
        providers=providers,
        errors=errors,
    )

    assert seed.identity_key in executed
    assert len(execution_service.calls) == 1
    assert execution_service.calls[0]["case_id"] is None
    assert rows[0]["lane"] == "Exploration"
    assert rows[0]["explorationOnly"] is True
    assert rows[0]["explorationPersisted"] is False
    assert rows[0]["findingMetadata"]["exploration_persisted"] is False
    assert providers[0]["lane"] == "Exploration"
    assert errors == []


def test_worker_source_does_not_persist_exploration_execution():
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    start = source.index("def _run_ephemeral_exploration(")
    end = source.index("def _exploration_identifiers(", start)
    method = source[start:end]

    assert "execution_service.execute_defaults(" in method
    assert "case_id=None" in method
    assert "persist_execution" not in method
    assert "enrich_target" not in method


def test_search_qml_exposes_exploration_graph_tab():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )

    assert '{ key: "exploration", label: "Explore" }' in qml
    assert "runData.explorationGraph" in qml
    assert "EXECUTED · EPHEMERAL" in qml
    assert "pivotScore" in qml
    assert "persistenceScore" in qml
