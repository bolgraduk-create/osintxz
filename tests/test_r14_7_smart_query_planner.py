from __future__ import annotations

from pathlib import Path

from app.application.exploration_graph import ExplorationGraph, ExplorationNode
from app.application.smart_query_planner import (
    build_smart_query_plan,
    graph_for_auto_execution,
)
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
)


def _node(
    *,
    kind=UnifiedSeedKind.USERNAME,
    value="alpha",
    quality=80.0,
    pivot=85.0,
    persistence=70.0,
    depth=1,
    source="Sherlock",
):
    seed = UnifiedSeed(
        kind=kind,
        value=value,
        origin="quality_exploration",
        depth=depth,
    )
    return ExplorationNode(
        seed=seed,
        observation_id="obs-1",
        quality_score=quality,
        pivot_score=pivot,
        persistence_score=persistence,
        reason="test",
        source=source,
        parent_seed_kind="username",
        parent_seed_value="root",
    )


def test_strong_exact_pivot_is_auto_executed():
    graph = ExplorationGraph(nodes=[_node()])
    plan = build_smart_query_plan(graph)

    assert len(plan.auto_nodes) == 1
    decision = plan.decisions[0]
    assert decision.action == "auto_execute"
    assert decision.route_hint == "classic + federation"
    assert "strong_pivot_score" in decision.signals


def test_moderate_pivot_is_review_only():
    graph = ExplorationGraph(
        nodes=[
            _node(
                quality=60.0,
                pivot=60.0,
                persistence=45.0,
            )
        ]
    )
    plan = build_smart_query_plan(graph)

    assert plan.auto_nodes == []
    assert len(plan.review_nodes) == 1
    assert plan.decisions[0].action == "review"


def test_weak_pivot_is_blocked():
    graph = ExplorationGraph(
        nodes=[
            _node(
                quality=42.0,
                pivot=35.0,
                persistence=20.0,
            )
        ]
    )
    plan = build_smart_query_plan(graph)

    assert plan.decisions[0].action == "blocked"
    assert "too weak" in plan.decisions[0].reason


def test_sensitive_source_never_auto_executes():
    graph = ExplorationGraph(
        nodes=[
            _node(
                source="darkweb_index",
                quality=95.0,
                pivot=95.0,
                persistence=90.0,
            )
        ]
    )
    plan = build_smart_query_plan(graph)

    assert plan.auto_nodes == []
    assert plan.decisions[0].action == "review"
    assert plan.decisions[0].risk == "guarded"


def test_auto_budget_retains_overflow_for_review():
    graph = ExplorationGraph(
        nodes=[
            _node(value=f"alpha{i}")
            for i in range(5)
        ]
    )
    plan = build_smart_query_plan(
        graph,
        max_auto=2,
    )

    assert len(plan.auto_nodes) == 2
    assert len(plan.review_nodes) == 3
    assert plan.to_dict()["summary"]["autoExecute"] == 2


def test_execution_graph_contains_only_auto_nodes():
    auto = _node(value="alpha")
    review = _node(
        value="beta",
        quality=60.0,
        pivot=60.0,
        persistence=50.0,
    )
    graph = ExplorationGraph(
        nodes=[auto, review]
    )
    plan = build_smart_query_plan(graph)
    execution = graph_for_auto_execution(
        graph,
        plan,
    )

    assert [node.seed.value for node in execution.nodes] == [
        "alpha"
    ]


def test_worker_uses_planner_before_ephemeral_execution():
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    planner_pos = worker.index(
        "smart_query_plan = build_smart_query_plan("
    )
    auto_graph_pos = worker.index(
        "auto_graph = graph_for_auto_execution("
    )
    execute_pos = worker.index(
        "self._run_ephemeral_exploration("
    )

    assert planner_pos < auto_graph_pos < execute_pos
    assert '"queryPlanner": smart_query_plan.to_dict()' in worker
    assert '"plannerAutoExecute": len(smart_query_plan.auto_nodes)' in worker
    assert '"plannerReview": len(smart_query_plan.review_nodes)' in worker


def test_search_ui_exposes_explainable_planner_tab():
    qml = Path(
        "app/interface/desktop/qml/pages/Search.qml"
    ).read_text(encoding="utf-8")

    for token in (
        '{ key: "planner", label: "Planner" }',
        'activeTab === "planner"',
        "runData.queryPlanner",
        'String(row.action || "review")',
        'String(row.routeHint || "review")',
        'String(row.risk || "normal")',
        '"No discovered pivots required a planner decision in this run."',
    ):
        assert token in qml
