from __future__ import annotations

from pathlib import Path

from app.application.search_quality_benchmark import (
    calculate_benchmark_metrics,
    evaluate_gate,
    load_benchmark_fixture,
    run_search_quality_benchmark,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "search_quality_benchmark"
    / "scenarios.json"
)


def test_fixture_loads_all_required_search_quality_scenarios():
    fixture = load_benchmark_fixture(FIXTURE)

    names = {
        str(item["name"])
        for item in fixture["scenarios"]
    }

    assert {
        "username_account_quality",
        "person_identity_quality",
        "url_scope_and_pivots",
        "organization_context_quality",
    }.issubset(names)


def test_benchmark_report_contains_core_quality_metrics():
    fixture = load_benchmark_fixture(FIXTURE)
    report = run_search_quality_benchmark(fixture)
    metrics = report.metrics

    assert metrics.observations >= 10
    assert metrics.useful_observations > 0
    assert 0.0 <= metrics.precision_at_10 <= 1.0
    assert 0.0 <= metrics.recall_at_100 <= 1.0
    assert 0.0 <= metrics.mrr <= 1.0
    assert 0.0 <= metrics.ndcg_at_20 <= 1.0
    assert 0.0 <= metrics.false_pivot_rate <= 1.0
    assert metrics.useful_pivots >= metrics.useful_pivots_found


def test_metrics_rank_good_rows_above_noise():
    rows = [
        {
            "_benchmarkRelevanceGrade": 3,
            "_benchmarkShouldExplore": True,
            "_benchmarkShouldPersist": True,
            "qualityWouldExplore": True,
            "qualityWouldPersist": True,
            "qualityLegacyVisible": True,
            "qualityLegacyPivotAllowed": True,
        },
        {
            "_benchmarkRelevanceGrade": 2,
            "_benchmarkShouldExplore": False,
            "_benchmarkShouldPersist": False,
            "qualityWouldExplore": False,
            "qualityWouldPersist": False,
            "qualityLegacyVisible": True,
            "qualityLegacyPivotAllowed": False,
        },
        {
            "_benchmarkRelevanceGrade": 0,
            "_benchmarkShouldExplore": False,
            "_benchmarkShouldPersist": False,
            "qualityWouldExplore": False,
            "qualityWouldPersist": False,
            "qualityLegacyVisible": True,
            "qualityLegacyPivotAllowed": False,
        },
    ]

    metrics = calculate_benchmark_metrics(rows)

    assert metrics.precision_at_10 == 2 / 3
    assert metrics.recall_at_100 == 1.0
    assert metrics.mrr == 1.0
    assert metrics.useful_pivots_found == 1
    assert metrics.false_pivots == 0
    assert metrics.persist_found == 1
    assert metrics.false_persist == 0


def test_gate_uses_fixture_thresholds_and_is_diagnostic():
    fixture = load_benchmark_fixture(FIXTURE)
    report = run_search_quality_benchmark(fixture)

    passed, failures = evaluate_gate(report, fixture["thresholds"])

    assert isinstance(passed, bool)
    assert isinstance(failures, list)
    assert all(isinstance(item, str) for item in failures)


def test_single_source_url_descendant_is_explorable_but_not_persisted():
    fixture = load_benchmark_fixture(FIXTURE)
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

    assert row["qualityWouldExplore"] is True
    assert row["qualityWouldPersist"] is False
    assert row["qualityPersistenceScore"] < 82
    assert any(
        "exploration" in signal.casefold()
        for signal in row["qualityNegativeSignals"]
    )


def test_benchmark_gate_requires_zero_false_persist():
    fixture = load_benchmark_fixture(FIXTURE)
    assert fixture["thresholds"]["falsePersist"] == 0

    report = run_search_quality_benchmark(fixture)
    passed, failures = evaluate_gate(report, fixture["thresholds"])

    assert report.metrics.false_persist == 0
    assert passed is True, failures


def test_username_dead_profile_is_ranked_as_noise():
    fixture = load_benchmark_fixture(FIXTURE)
    report = run_search_quality_benchmark(fixture)

    username = next(
        scenario
        for scenario in report.scenarios
        if scenario.name == "username_account_quality"
    )
    row = next(
        item
        for item in username.rows
        if item["_benchmarkId"] == "username-dead-profile"
    )

    assert row["qualityTier"] == "noise"
    assert row["qualityWouldExplore"] is False
    assert row["qualityWouldPersist"] is False


def test_browser_likely_account_is_visible_but_not_auto_pivoted_or_persisted():
    fixture = load_benchmark_fixture(FIXTURE)
    report = run_search_quality_benchmark(fixture)

    username = next(
        scenario
        for scenario in report.scenarios
        if scenario.name == "username_account_quality"
    )
    row = next(
        item
        for item in username.rows
        if item["_benchmarkId"] == "username-reddit-likely"
    )

    assert row["qualityWouldShow"] is True
    assert row["qualityWouldExplore"] is False
    assert row["qualityWouldPersist"] is False


def test_cli_gate_exists_and_writes_report():
    text = Path(
        "tools/run_r13_26b_search_quality_benchmark.py"
    ).read_text(encoding="utf-8")

    assert "search_quality_benchmark_latest.json" in text
    assert "GATE: PASS" in text
    assert "GATE: FAIL" in text
