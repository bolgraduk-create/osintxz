from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.search_retrieval_scheduler import (
    RetrievalScheduleBook,
    schedule_seed_routes,
    schedule_seeds,
)
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
)


@dataclass(frozen=True)
class _Route:
    source_code: str
    capability: str
    configured: bool = True


def test_seed_scheduler_gives_each_kind_a_first_wave_before_second_same_kind():
    seeds = [
        UnifiedSeed(UnifiedSeedKind.USERNAME, "alpha"),
        UnifiedSeed(UnifiedSeedKind.USERNAME, "bravo"),
        UnifiedSeed(UnifiedSeedKind.USERNAME, "charlie"),
        UnifiedSeed(UnifiedSeedKind.EMAIL, "alice@example.org"),
        UnifiedSeed(UnifiedSeedKind.DOMAIN, "example.org"),
    ]

    selected, summary = schedule_seeds(
        seeds,
        limit=3,
        lane="root",
    )

    assert {seed.kind for seed in selected} == {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.DOMAIN,
    }
    assert summary.selected == 3
    assert summary.skipped_due_to_budget == 2
    assert summary.waves == 1


def test_route_scheduler_round_robins_across_seed_identity():
    first = UnifiedSeed(UnifiedSeedKind.USERNAME, "alpha")
    second = UnifiedSeed(UnifiedSeedKind.EMAIL, "alice@example.org")
    items = [
        (first, _Route("a", "username")),
        (first, _Route("b", "username")),
        (first, _Route("c", "username")),
        (second, _Route("mail", "email")),
    ]

    selected, summary = schedule_seed_routes(
        items,
        limit=2,
        lane="federation",
    )

    assert {seed.identity_key for seed, _route in selected} == {
        first.identity_key,
        second.identity_key,
    }
    assert summary.selected == 2
    assert summary.skipped_due_to_budget == 2
    assert summary.groups == 2
    assert summary.waves == 1


def test_route_scheduler_prefers_configured_route_inside_seed_group():
    seed = UnifiedSeed(UnifiedSeedKind.DOMAIN, "example.org")
    unconfigured = _Route("a-disabled", "domain", configured=False)
    configured = _Route("z-ready", "domain", configured=True)

    selected, summary = schedule_seed_routes(
        [(seed, unconfigured), (seed, configured)],
        limit=1,
        lane="federation",
    )

    assert selected == [(seed, configured)]
    decision = next(item for item in summary.decisions if item.selected)
    assert decision.source == "z-ready"
    assert decision.wave == 1


def test_schedule_book_reports_exact_budget_misses():
    seeds = [
        UnifiedSeed(UnifiedSeedKind.USERNAME, "alpha"),
        UnifiedSeed(UnifiedSeedKind.USERNAME, "bravo"),
        UnifiedSeed(UnifiedSeedKind.EMAIL, "alice@example.org"),
    ]
    _selected, first = schedule_seeds(
        seeds,
        limit=2,
        lane="classic",
    )
    _selected, second = schedule_seed_routes(
        [
            (
                seeds[0],
                _Route("one", "username"),
            ),
            (
                seeds[0],
                _Route("two", "username"),
            ),
        ],
        limit=1,
        lane="federation",
    )

    book = RetrievalScheduleBook()
    book.add(first)
    book.add(second)

    payload = book.to_dict()
    assert book.candidates == 5
    assert book.selected == 3
    assert book.missed_due_to_budget == 2
    assert payload["summary"]["missedDueToBudget"] == 2


def test_zero_budget_marks_every_candidate_as_budget_skip():
    seeds = [
        UnifiedSeed(UnifiedSeedKind.EMAIL, "a@example.org"),
        UnifiedSeed(UnifiedSeedKind.DOMAIN, "example.org"),
    ]

    selected, summary = schedule_seeds(
        seeds,
        limit=0,
        lane="disabled",
    )

    assert selected == []
    assert summary.skipped_due_to_budget == 2
    assert all(not item.selected for item in summary.decisions)


def test_worker_uses_scheduler_instead_of_first_n_route_slices():
    text = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "schedule_seeds(" in text
    assert "schedule_seed_routes(" in text
    assert '"retrievalSchedule": retrieval_schedule.to_dict()' in text
    assert '"missedDueToBudget": retrieval_schedule.missed_due_to_budget' in text

    assert "plan.federation_routes[: self.FEDERATION_ROUTE_LIMIT]" not in text
    assert "plan.registry_queries[: self.REGISTRY_QUERY_LIMIT]" not in text
    assert "pivot_plan.federation_routes[:24]" not in text
    assert "pivot_plan.registry_queries[:10]" not in text


def test_search_qml_exposes_schedule_decisions_and_budget_misses():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )

    assert '{ key: "schedule", label: "Schedule" }' in qml
    assert "retrievalScheduleRows()" in qml
    assert "BUDGET SKIP" in qml
    assert "missedDueToBudget" in qml
    assert "row.wave" in qml


def test_search_quality_and_exploration_paths_remain_present():
    text = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "annotate_search_quality_rows(" in text
    assert "build_exploration_graph(" in text
    assert "_run_ephemeral_exploration(" in text
