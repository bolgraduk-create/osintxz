from __future__ import annotations

from pathlib import Path

from app.application.exploration_graph import (
    ExplorationGraph,
    ExplorationNode,
    build_exploration_graph,
)
from app.application.smart_query_planner import (
    build_smart_query_plan,
    graph_for_lane_execution,
    nodes_for_lane,
)
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
)


def _node(kind, value, *, quality=88.0, pivot=90.0, persistence=75.0):
    return ExplorationNode(
        seed=UnifiedSeed(
            kind=kind,
            value=value,
            origin="quality_exploration",
            depth=1,
        ),
        observation_id="obs-1",
        quality_score=quality,
        pivot_score=pivot,
        persistence_score=persistence,
        reason="test",
        source="test_source",
    )


def test_domain_uses_safe_multilane_auto_execution():
    graph = ExplorationGraph(
        nodes=[_node(UnifiedSeedKind.DOMAIN, "example.org")]
    )
    plan = build_smart_query_plan(graph)
    decision = plan.decisions[0]

    assert decision.action == "auto_execute"
    assert decision.auto_lanes == (
        "classic",
        "federation",
        "open_web",
    )
    assert decision.review_lanes == ()
    assert decision.route_hint == "classic + open web + federation"


def test_registry_exact_identifier_can_enter_exploration_graph():
    rows = [
        {
            "qualityWouldExplore": True,
            "qualityPivotScore": 91.0,
            "qualityScore": 87.0,
            "qualityPersistenceScore": 76.0,
            "qualityObservationId": "obs-company",
            "identifiers": {
                "registration_id": "BG123456789",
            },
            "depth": 0,
            "source": "company_registry",
        }
    ]

    graph = build_exploration_graph(
        rows,
        max_nodes=8,
        max_depth=2,
    )

    assert len(graph.nodes) == 1
    assert graph.nodes[0].seed.kind is UnifiedSeedKind.REGISTRATION_ID
    assert graph.nodes[0].seed.value == "BG123456789"


def test_registry_identifier_routes_only_to_registry():
    graph = ExplorationGraph(
        nodes=[
            _node(
                UnifiedSeedKind.REGISTRATION_ID,
                "BG123456789",
            )
        ]
    )
    plan = build_smart_query_plan(graph)
    decision = plan.decisions[0]

    assert decision.action == "auto_execute"
    assert decision.auto_lanes == ("registry",)
    assert decision.review_lanes == ()
    assert decision.route_hint == "registry"
    assert nodes_for_lane(plan, "classic") == []
    assert len(nodes_for_lane(plan, "registry")) == 1


def test_lane_execution_graph_contains_only_matching_nodes():
    classic = _node(
        UnifiedSeedKind.USERNAME,
        "alpha",
    )
    registry = _node(
        UnifiedSeedKind.VAT_ID,
        "BG123456789",
    )
    graph = ExplorationGraph(nodes=[classic, registry])
    plan = build_smart_query_plan(graph)

    classic_graph = graph_for_lane_execution(
        graph,
        plan,
        "classic",
    )
    registry_graph = graph_for_lane_execution(
        graph,
        plan,
        "registry",
    )

    assert [node.seed.value for node in classic_graph.nodes] == [
        "alpha"
    ]
    assert [node.seed.value for node in registry_graph.nodes] == [
        "BG123456789"
    ]


def test_worker_executes_planner_federation_and_registry_through_existing_boundaries():
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    for token in (
        'nodes_for_lane(\n                    smart_query_plan,\n                    "federation",',
        'lane="planner_federation"',
        "self._run_federation_routes(",
        'nodes_for_lane(\n                    smart_query_plan,\n                    "registry",',
        'lane="planner_registry"',
        "self._run_registry_queries(",
        '"plannerFederationExecuted"',
        '"plannerRegistryExecuted"',
        '"plannerOpenWebReview"',
    ):
        assert token in worker

    # R14.9 upgrades Open Web only through the explicit no-persistence
    # enrichment boundary. The persisted enrich(...) call is not used here.
    assert 'lane="planner_open_web"' in worker
    assert ".enrich_ephemeral(query)" in worker


def test_planner_ui_explains_auto_and_review_lanes():
    qml = Path(
        "app/interface/desktop/qml/pages/Search.qml"
    ).read_text(encoding="utf-8")

    for token in (
        "row.autoLanes",
        "row.reviewLanes",
        '" · auto " + autoLanes.join(" + ")',
        '" · review " + reviewLanes.join(" + ")',
        '{ key: "planner", label: "Planner" }',
    ):
        assert token in qml
