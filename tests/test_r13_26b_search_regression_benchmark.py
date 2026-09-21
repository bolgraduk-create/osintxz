from __future__ import annotations

from pathlib import Path

from app.application.search_regression_benchmark import (
    evaluate_search_benchmark,
    evaluate_search_benchmark_case,
    load_search_benchmark_fixture,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "search_quality_benchmark"
    / "v1.json"
)


def test_search_quality_benchmark_fixture_meets_current_baseline():
    report = evaluate_search_benchmark(
        load_search_benchmark_fixture(FIXTURE)
    )

    assert report.passed, "\n".join(report.failures)
    assert report.totals["cases"] >= 4
    assert report.totals["judged"] >= 15
    assert report.totals["invalidAccountLeakage"] == 0


def test_username_case_keeps_verified_and_likely_without_invalid_leakage():
    fixture = load_search_benchmark_fixture(FIXTURE)
    case = next(
        item
        for item in fixture["cases"]
        if item["id"] == "username_account_availability"
    )
    metrics = evaluate_search_benchmark_case(case)

    assert metrics.recall_at_100 == 1.0
    assert metrics.precision_at_10 == 1.0
    assert metrics.invalid_account_leakage == 0
    assert metrics.useful_pivot_recall == 1.0
    assert metrics.persistence_precision == 1.0


def test_person_name_case_keeps_transliterations_and_rejects_name_collisions():
    fixture = load_search_benchmark_fixture(FIXTURE)
    case = next(
        item
        for item in fixture["cases"]
        if item["id"] == "person_name_transliteration"
    )
    metrics = evaluate_search_benchmark_case(case)

    assert metrics.recall_at_100 == 1.0
    assert metrics.precision_at_10 == 1.0
    assert metrics.noise_top_20 == 0


def test_url_scope_case_rejects_unrelated_same_host_path():
    fixture = load_search_benchmark_fixture(FIXTURE)
    case = next(
        item
        for item in fixture["cases"]
        if item["id"] == "url_scope"
    )
    metrics = evaluate_search_benchmark_case(case)

    assert metrics.recall_at_100 == 1.0
    assert metrics.precision_at_10 == 1.0
    assert metrics.false_pivot_rate == 0.0


def test_benchmark_metrics_detect_a_deliberate_quality_regression():
    fixture = load_search_benchmark_fixture(FIXTURE)
    fixture["thresholds"]["precisionAt10Min"] = 1.01

    report = evaluate_search_benchmark(fixture)

    assert report.passed is False
    assert any(
        "precisionAt10" in failure
        for failure in report.failures
    )


def test_benchmark_report_is_json_serializable_shape():
    report = evaluate_search_benchmark(
        load_search_benchmark_fixture(FIXTURE)
    )
    payload = report.to_dict()

    assert payload["cases"]
    assert "macro" in payload
    assert "totals" in payload
    assert "thresholds" in payload
    assert isinstance(payload["failures"], list)
