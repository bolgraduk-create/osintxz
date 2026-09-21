from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.search_retrieval_scheduler import (
    AdaptiveRetrievalFeedback,
    RetrievalScheduleBook,
    schedule_seed_routes,
)
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
)


@dataclass(frozen=True)
class _Route:
    source_code: str
    capability: str = "lookup"
    configured: bool = True
    timeout: int = 20


def _seed(value: str = "alpha") -> UnifiedSeed:
    return UnifiedSeed(UnifiedSeedKind.USERNAME, value)


def test_feedback_classifies_timeout_and_tracks_latency():
    feedback = AdaptiveRetrievalFeedback()

    feedback.observe_provider_row(
        {
            "source": "slow_source",
            "status": "failed",
            "detail": "request timed out after 18 seconds",
            "records": 0,
            "durationSeconds": 18.2,
        }
    )

    observation = feedback.observation("slow_source")

    assert observation is not None
    assert observation.attempts == 1
    assert observation.dominant_state == "timeout"
    assert observation.timeout_risk == 1.0
    assert observation.health_penalty >= 5.0
    assert observation.average_seconds == 18.2


def test_adaptive_scheduler_prefers_fast_healthy_route_for_same_seed():
    seed = _seed()
    feedback = AdaptiveRetrievalFeedback()

    feedback.observe_provider_row(
        {
            "source": "fast",
            "status": "success",
            "records": 2,
            "durationSeconds": 0.8,
        }
    )
    feedback.observe_provider_row(
        {
            "source": "slow",
            "status": "failed",
            "detail": "timeout",
            "records": 0,
            "durationSeconds": 18.0,
        }
    )

    fast = _Route("fast")
    slow = _Route("slow")

    selected, summary = schedule_seed_routes(
        [(seed, slow), (seed, fast)],
        limit=1,
        lane="federation_pivots",
        feedback=feedback,
        time_budget_seconds=96.0,
    )

    assert selected == [(seed, fast)]
    chosen = next(item for item in summary.decisions if item.selected)
    rejected = next(item for item in summary.decisions if item.source == "slow")

    assert chosen.health_state == "ready"
    assert chosen.estimated_seconds < rejected.estimated_seconds
    assert rejected.deprioritized is True
    assert rejected.timeout_risk == 1.0


def test_time_budget_skips_expensive_second_route_but_keeps_first():
    seed = _seed()
    feedback = AdaptiveRetrievalFeedback()

    feedback.observe_provider_row(
        {
            "source": "one",
            "status": "success",
            "records": 1,
            "durationSeconds": 4.0,
        }
    )
    feedback.observe_provider_row(
        {
            "source": "two",
            "status": "success",
            "records": 1,
            "durationSeconds": 9.0,
        }
    )

    selected, summary = schedule_seed_routes(
        [(seed, _Route("one")), (seed, _Route("two"))],
        limit=2,
        lane="federation_pivots",
        feedback=feedback,
        time_budget_seconds=6.0,
    )

    assert len(selected) == 1
    assert selected[0][1].source_code == "one"
    assert summary.skipped_due_to_time_budget == 1
    skipped = next(item for item in summary.decisions if not item.selected)
    assert skipped.time_budget_skip is True
    assert "time budget" in skipped.reason


def test_adaptive_health_does_not_break_seed_fairness():
    first = _seed("alpha")
    second = UnifiedSeed(UnifiedSeedKind.EMAIL, "alice@example.org")
    feedback = AdaptiveRetrievalFeedback()

    feedback.observe_provider_row(
        {
            "source": "alpha_slow",
            "status": "failed",
            "detail": "timeout",
            "durationSeconds": 15.0,
            "records": 0,
        }
    )

    selected, summary = schedule_seed_routes(
        [
            (first, _Route("alpha_slow")),
            (first, _Route("alpha_fast")),
            (second, _Route("mail")),
        ],
        limit=2,
        lane="federation_pivots",
        feedback=feedback,
        time_budget_seconds=40.0,
    )

    assert {seed.identity_key for seed, _route in selected} == {
        first.identity_key,
        second.identity_key,
    }
    assert summary.groups == 2
    assert summary.waves == 1


def test_schedule_book_aggregates_time_budget_telemetry():
    seed = _seed()
    feedback = AdaptiveRetrievalFeedback()
    feedback.observe_provider_row(
        {
            "source": "slow",
            "status": "failed",
            "detail": "timeout",
            "durationSeconds": 18.0,
            "records": 0,
        }
    )

    _selected, summary = schedule_seed_routes(
        [(seed, _Route("slow")), (seed, _Route("other"))],
        limit=2,
        lane="federation_pivots",
        feedback=feedback,
        time_budget_seconds=5.0,
    )

    book = RetrievalScheduleBook()
    book.add(summary)
    payload = book.to_dict()["summary"]

    assert payload["estimatedSelectedSeconds"] > 0
    assert payload["deprioritized"] >= 1
    assert payload["skippedDueToTimeBudget"] >= 1


def test_worker_records_duration_and_runtime_feedback():
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "AdaptiveRetrievalFeedback" in source
    assert "route_started = perf_counter()" in source
    assert "query_started = perf_counter()" in source
    assert 'provider_row["durationSeconds"]' in source
    assert "feedback.observe_provider_row(provider_row)" in source
    assert '"retrievalFeedback": retrieval_feedback.to_dict()' in source
    assert '"skippedDueToTimeBudget"' in source
    assert '"retrievalDeprioritized"' in source


def test_pivot_route_scheduler_receives_runtime_feedback_and_time_budget():
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "PIVOT_FEDERATION_TIME_BUDGET = 96.0" in source
    assert "PIVOT_REGISTRY_TIME_BUDGET = 50.0" in source
    assert "feedback=retrieval_feedback" in source
    assert "time_budget_seconds=(" in source


def test_fair_scheduler_regression_contract_stays_present():
    source = Path(
        "app/application/search_retrieval_scheduler.py"
    ).read_text(encoding="utf-8")

    assert "selected by adaptive fair round-robin" in source
    assert "grouped.setdefault(seed.identity_key" in source
    assert "AdaptiveRetrievalFeedback" in source
    assert "time_budget_seconds" in source
