"""R13.26b — deterministic search regression benchmark.

The benchmark is intentionally offline.  It evaluates the current search-quality
and consolidation stack against curated observations that represent regressions
already seen in OSINTXZ.

It is not a replacement for unit tests.  Unit tests answer "did this rule still
behave exactly as coded?".  The benchmark answers "did the overall search get
better or worse?" using retrieval/ranking metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable

from app.application.investigation_result_consolidation import (
    consolidate_result_rows,
)
from app.application.search_quality_engine import annotate_search_quality_rows


@dataclass(frozen=True, slots=True)
class BenchmarkCaseMetrics:
    case_id: str
    total_judged: int
    relevant_total: int
    shown_total: int
    recall_at_100: float
    precision_at_10: float
    reciprocal_rank: float
    ndcg_at_20: float
    clean_precision: float
    clean_recall: float
    useful_pivot_recall: float
    false_pivot_rate: float
    persistence_precision: float
    legacy_missed_due_to_gate: int
    quality_missed_due_to_gate: int
    noise_top_20: int
    invalid_account_leakage: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "totalJudged": self.total_judged,
            "relevantTotal": self.relevant_total,
            "shownTotal": self.shown_total,
            "recallAt100": round(self.recall_at_100, 4),
            "precisionAt10": round(self.precision_at_10, 4),
            "mrr": round(self.reciprocal_rank, 4),
            "ndcgAt20": round(self.ndcg_at_20, 4),
            "cleanPrecision": round(self.clean_precision, 4),
            "cleanRecall": round(self.clean_recall, 4),
            "usefulPivotRecall": round(self.useful_pivot_recall, 4),
            "falsePivotRate": round(self.false_pivot_rate, 4),
            "persistencePrecision": round(self.persistence_precision, 4),
            "legacyMissedDueToGate": self.legacy_missed_due_to_gate,
            "qualityMissedDueToGate": self.quality_missed_due_to_gate,
            "noiseTop20": self.noise_top_20,
            "invalidAccountLeakage": self.invalid_account_leakage,
        }


@dataclass(frozen=True, slots=True)
class SearchBenchmarkReport:
    cases: tuple[BenchmarkCaseMetrics, ...]
    macro: dict[str, float]
    totals: dict[str, int]
    thresholds: dict[str, float | int]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "macro": {
                key: round(float(value), 4)
                for key, value in self.macro.items()
            },
            "totals": dict(self.totals),
            "thresholds": dict(self.thresholds),
            "failures": list(self.failures),
            "cases": [case.to_dict() for case in self.cases],
        }


def load_search_benchmark_fixture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Search benchmark fixture must be a JSON object.")
    if not isinstance(payload.get("cases"), list):
        raise ValueError("Search benchmark fixture requires a cases array.")
    return payload


def evaluate_search_benchmark(
    fixture: dict[str, Any],
) -> SearchBenchmarkReport:
    cases = tuple(
        evaluate_search_benchmark_case(case)
        for case in list(fixture.get("cases") or [])
        if isinstance(case, dict)
    )
    if not cases:
        raise ValueError("Search benchmark fixture contains no valid cases.")

    macro = {
        "recallAt100": _mean(case.recall_at_100 for case in cases),
        "precisionAt10": _mean(case.precision_at_10 for case in cases),
        "mrr": _mean(case.reciprocal_rank for case in cases),
        "ndcgAt20": _mean(case.ndcg_at_20 for case in cases),
        "cleanPrecision": _mean(case.clean_precision for case in cases),
        "cleanRecall": _mean(case.clean_recall for case in cases),
        "usefulPivotRecall": _mean(case.useful_pivot_recall for case in cases),
        "falsePivotRate": _mean(case.false_pivot_rate for case in cases),
        "persistencePrecision": _mean(
            case.persistence_precision for case in cases
        ),
    }
    totals = {
        "cases": len(cases),
        "judged": sum(case.total_judged for case in cases),
        "relevant": sum(case.relevant_total for case in cases),
        "legacyMissedDueToGate": sum(
            case.legacy_missed_due_to_gate for case in cases
        ),
        "qualityMissedDueToGate": sum(
            case.quality_missed_due_to_gate for case in cases
        ),
        "noiseTop20": sum(case.noise_top_20 for case in cases),
        "invalidAccountLeakage": sum(
            case.invalid_account_leakage for case in cases
        ),
    }
    thresholds = dict(fixture.get("thresholds") or {})
    failures = tuple(
        _threshold_failures(
            macro=macro,
            totals=totals,
            thresholds=thresholds,
        )
    )
    return SearchBenchmarkReport(
        cases=cases,
        macro=macro,
        totals=totals,
        thresholds=thresholds,
        failures=failures,
    )


def evaluate_search_benchmark_case(
    case: dict[str, Any],
) -> BenchmarkCaseMetrics:
    case_id = str(case.get("id") or "").strip()
    if not case_id:
        raise ValueError("Every benchmark case requires an id.")

    rows = [
        dict(row)
        for row in list(case.get("rows") or [])
        if isinstance(row, dict)
    ]
    judgments = _judgment_map(case)
    if not rows or not judgments:
        raise ValueError(
            f"Benchmark case {case_id!r} requires rows and judgments."
        )

    search_profile = (
        dict(case.get("searchProfile"))
        if isinstance(case.get("searchProfile"), dict)
        else {}
    )
    seeds = [
        dict(seed)
        for seed in list(case.get("seeds") or [])
        if isinstance(seed, dict)
    ]

    annotated, _quality_summary = annotate_search_quality_rows(
        rows,
        search_profile=search_profile,
    )
    consolidated = consolidate_result_rows(
        annotated,
        seeds=seeds,
        search_profile=search_profile,
        limit=max(220, len(annotated) * 2),
    )

    by_id = _best_rows_by_benchmark_id(annotated)
    shown = sorted(
        (
            row for row in by_id.values()
            if bool(row.get("qualityWouldShow"))
        ),
        key=_quality_rank_key,
    )

    relevant_ids = {
        benchmark_id
        for benchmark_id, judgment in judgments.items()
        if int(judgment.get("relevance") or 0) > 0
    }
    shown_ids = [
        str(row.get("benchmarkId") or "")
        for row in shown[:100]
        if str(row.get("benchmarkId") or "") in judgments
    ]

    recall_at_100 = _safe_ratio(
        len(relevant_ids.intersection(shown_ids)),
        len(relevant_ids),
        empty=1.0,
    )

    top_10_ids = shown_ids[:10]
    precision_at_10 = _safe_ratio(
        sum(
            int(judgments[item].get("relevance") or 0) > 0
            for item in top_10_ids
        ),
        len(top_10_ids),
        empty=1.0,
    )

    reciprocal_rank = 0.0
    for rank, benchmark_id in enumerate(shown_ids, start=1):
        if int(judgments[benchmark_id].get("relevance") or 0) > 0:
            reciprocal_rank = 1.0 / float(rank)
            break

    ranked_grades = [
        int(judgments[item].get("relevance") or 0)
        for item in shown_ids[:20]
    ]
    ideal_grades = sorted(
        (
            int(judgment.get("relevance") or 0)
            for judgment in judgments.values()
        ),
        reverse=True,
    )[:20]
    ndcg_at_20 = _ndcg(ranked_grades, ideal_grades)

    clean_ids = _output_ids(
        list(consolidated.rows or [])
        + list(consolidated.related_accounts or [])
    )
    clean_relevant = len(relevant_ids.intersection(clean_ids))
    clean_precision = _safe_ratio(
        sum(
            int(judgments[item].get("relevance") or 0) > 0
            for item in clean_ids
            if item in judgments
        ),
        sum(1 for item in clean_ids if item in judgments),
        empty=1.0,
    )
    clean_recall = _safe_ratio(
        clean_relevant,
        len(relevant_ids),
        empty=1.0,
    )

    expected_pivots = {
        benchmark_id
        for benchmark_id, judgment in judgments.items()
        if bool(judgment.get("expectedExplore"))
    }
    actual_pivots = {
        benchmark_id
        for benchmark_id, row in by_id.items()
        if bool(row.get("qualityWouldExplore"))
    }
    useful_pivot_recall = _safe_ratio(
        len(expected_pivots.intersection(actual_pivots)),
        len(expected_pivots),
        empty=1.0,
    )
    false_pivot_rate = _safe_ratio(
        sum(
            benchmark_id not in expected_pivots
            for benchmark_id in actual_pivots
            if benchmark_id in judgments
        ),
        sum(
            benchmark_id in judgments
            for benchmark_id in actual_pivots
        ),
        empty=0.0,
    )

    expected_persist = {
        benchmark_id
        for benchmark_id, judgment in judgments.items()
        if bool(judgment.get("expectedPersist"))
    }
    actual_persist = {
        benchmark_id
        for benchmark_id, row in by_id.items()
        if bool(row.get("qualityWouldPersist"))
    }
    persistence_precision = _safe_ratio(
        len(expected_persist.intersection(actual_persist)),
        sum(
            benchmark_id in judgments
            for benchmark_id in actual_persist
        ),
        empty=1.0,
    )

    expected_visible = {
        benchmark_id
        for benchmark_id, judgment in judgments.items()
        if bool(judgment.get("expectedShow"))
    }
    legacy_missed_due_to_gate = sum(
        1
        for benchmark_id in expected_visible
        if benchmark_id in by_id
        and not bool(by_id[benchmark_id].get("qualityLegacyVisible"))
    )
    quality_missed_due_to_gate = sum(
        1
        for benchmark_id in expected_visible
        if benchmark_id in by_id
        and not bool(by_id[benchmark_id].get("qualityWouldShow"))
    )

    noise_top_20 = sum(
        int(judgments[item].get("relevance") or 0) <= 0
        for item in shown_ids[:20]
        if item in judgments
    )

    invalid_ids = {
        benchmark_id
        for benchmark_id, judgment in judgments.items()
        if bool(judgment.get("invalidAccount"))
    }
    invalid_account_leakage = len(invalid_ids.intersection(clean_ids))

    return BenchmarkCaseMetrics(
        case_id=case_id,
        total_judged=len(judgments),
        relevant_total=len(relevant_ids),
        shown_total=len(shown_ids),
        recall_at_100=recall_at_100,
        precision_at_10=precision_at_10,
        reciprocal_rank=reciprocal_rank,
        ndcg_at_20=ndcg_at_20,
        clean_precision=clean_precision,
        clean_recall=clean_recall,
        useful_pivot_recall=useful_pivot_recall,
        false_pivot_rate=false_pivot_rate,
        persistence_precision=persistence_precision,
        legacy_missed_due_to_gate=legacy_missed_due_to_gate,
        quality_missed_due_to_gate=quality_missed_due_to_gate,
        noise_top_20=noise_top_20,
        invalid_account_leakage=invalid_account_leakage,
    )


def _judgment_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in list(case.get("judgments") or []):
        if not isinstance(item, dict):
            continue
        benchmark_id = str(item.get("benchmarkId") or "").strip()
        if benchmark_id:
            out[benchmark_id] = dict(item)
    return out


def _best_rows_by_benchmark_id(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        benchmark_id = str(row.get("benchmarkId") or "").strip()
        if not benchmark_id:
            continue
        previous = out.get(benchmark_id)
        if previous is None or _quality_rank_key(row) < _quality_rank_key(previous):
            out[benchmark_id] = row
    return out


def _quality_rank_key(row: dict[str, Any]) -> tuple[float, float, str]:
    return (
        -_safe_float(row.get("qualityScore")),
        -_safe_float(row.get("qualityRelevanceScore")),
        str(row.get("benchmarkId") or ""),
    )


def _output_ids(rows: Iterable[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("benchmarkId") or "").strip()
        for row in rows
        if str(row.get("benchmarkId") or "").strip()
    }


def _ndcg(actual: list[int], ideal: list[int]) -> float:
    ideal_score = _dcg(ideal)
    if ideal_score <= 0:
        return 1.0
    return min(1.0, _dcg(actual) / ideal_score)


def _dcg(grades: list[int]) -> float:
    return sum(
        ((2.0 ** max(0, int(grade))) - 1.0)
        / math.log2(index + 2.0)
        for index, grade in enumerate(grades)
    )


def _threshold_failures(
    *,
    macro: dict[str, float],
    totals: dict[str, int],
    thresholds: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    minimums = {
        "recallAt100Min": "recallAt100",
        "precisionAt10Min": "precisionAt10",
        "mrrMin": "mrr",
        "ndcgAt20Min": "ndcgAt20",
        "cleanPrecisionMin": "cleanPrecision",
        "cleanRecallMin": "cleanRecall",
        "usefulPivotRecallMin": "usefulPivotRecall",
        "persistencePrecisionMin": "persistencePrecision",
    }
    maximums = {
        "falsePivotRateMax": "falsePivotRate",
    }
    total_maximums = {
        "qualityMissedDueToGateMax": "qualityMissedDueToGate",
        "noiseTop20Max": "noiseTop20",
        "invalidAccountLeakageMax": "invalidAccountLeakage",
    }

    for threshold_key, metric_key in minimums.items():
        if threshold_key not in thresholds:
            continue
        actual = float(macro.get(metric_key) or 0.0)
        expected = float(thresholds[threshold_key])
        if actual + 1e-9 < expected:
            failures.append(
                f"{metric_key}={actual:.4f} is below minimum {expected:.4f}"
            )

    for threshold_key, metric_key in maximums.items():
        if threshold_key not in thresholds:
            continue
        actual = float(macro.get(metric_key) or 0.0)
        expected = float(thresholds[threshold_key])
        if actual - 1e-9 > expected:
            failures.append(
                f"{metric_key}={actual:.4f} exceeds maximum {expected:.4f}"
            )

    for threshold_key, metric_key in total_maximums.items():
        if threshold_key not in thresholds:
            continue
        actual = int(totals.get(metric_key) or 0)
        expected = int(thresholds[threshold_key])
        if actual > expected:
            failures.append(
                f"{metric_key}={actual} exceeds maximum {expected}"
            )

    return failures


def _safe_ratio(
    numerator: int | float,
    denominator: int | float,
    *,
    empty: float,
) -> float:
    if not denominator:
        return float(empty)
    return float(numerator) / float(denominator)


def _mean(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
