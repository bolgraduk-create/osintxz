"""R13.26b — deterministic Search Quality regression benchmark.

This benchmark is intentionally offline. It evaluates the production shadow
Search Quality Engine against labelled synthetic OSINT observations and reports
ranking/retrieval metrics without network, browser, database or external tools.

Labels:
  relevance_grade: 0=noise, 1=possible, 2=relevant, 3=strong
  should_explore: whether an exploratory pivot would be useful
  should_persist: whether the observation is strong enough to persist

The benchmark is diagnostic first. Thresholds are deliberately conservative and
can be raised only after several real-world searches are manually reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable

from app.application.search_quality_engine import (
    annotate_search_quality_rows,
)


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    observations: int
    useful_observations: int
    precision_at_10: float
    recall_at_100: float
    mrr: float
    ndcg_at_20: float
    useful_pivots: int
    useful_pivots_found: int
    false_pivots: int
    predicted_pivots: int
    false_pivot_rate: float
    persist_expected: int
    persist_found: int
    false_persist: int
    missed_by_legacy_visibility: int
    missed_by_legacy_pivot: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "observations": self.observations,
            "usefulObservations": self.useful_observations,
            "precisionAt10": round(self.precision_at_10, 4),
            "recallAt100": round(self.recall_at_100, 4),
            "mrr": round(self.mrr, 4),
            "ndcgAt20": round(self.ndcg_at_20, 4),
            "usefulPivots": self.useful_pivots,
            "usefulPivotsFound": self.useful_pivots_found,
            "falsePivots": self.false_pivots,
            "predictedPivots": self.predicted_pivots,
            "falsePivotRate": round(self.false_pivot_rate, 4),
            "persistExpected": self.persist_expected,
            "persistFound": self.persist_found,
            "falsePersist": self.false_persist,
            "missedByLegacyVisibility": self.missed_by_legacy_visibility,
            "missedByLegacyPivot": self.missed_by_legacy_pivot,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkScenarioResult:
    name: str
    description: str
    rows: tuple[dict[str, Any], ...]
    metrics: BenchmarkMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "metrics": self.metrics.to_dict(),
            "rows": [dict(row) for row in self.rows],
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    scenarios: tuple[BenchmarkScenarioResult, ...]
    metrics: BenchmarkMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


def load_benchmark_fixture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark fixture root must be an object.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Benchmark fixture must contain non-empty scenarios.")
    return payload


def run_search_quality_benchmark(
    fixture: dict[str, Any],
) -> BenchmarkReport:
    scenario_results: list[BenchmarkScenarioResult] = []
    all_rows: list[dict[str, Any]] = []

    for scenario in fixture.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        name = str(scenario.get("name") or "unnamed")
        description = str(scenario.get("description") or "")
        profile = scenario.get("searchProfile")
        profile = profile if isinstance(profile, dict) else {}
        raw_rows = scenario.get("rows")
        raw_rows = raw_rows if isinstance(raw_rows, list) else []

        prepared: list[dict[str, Any]] = []
        for index, item in enumerate(raw_rows):
            if not isinstance(item, dict):
                continue
            row = dict(item.get("row") or {})
            expected = item.get("expected")
            expected = expected if isinstance(expected, dict) else {}
            row["_benchmarkScenario"] = name
            row["_benchmarkId"] = str(
                item.get("id") or f"{name}-{index + 1}"
            )
            row["_benchmarkRelevanceGrade"] = _clamp_grade(
                expected.get("relevanceGrade")
            )
            row["_benchmarkShouldExplore"] = bool(
                expected.get("shouldExplore")
            )
            row["_benchmarkShouldPersist"] = bool(
                expected.get("shouldPersist")
            )
            prepared.append(row)

        annotated, _summary = annotate_search_quality_rows(
            prepared,
            search_profile=profile,
        )
        ranked = tuple(
            sorted(
                annotated,
                key=lambda row: (
                    -float(row.get("qualityScore") or 0.0),
                    str(row.get("_benchmarkId") or ""),
                ),
            )
        )
        metrics = calculate_benchmark_metrics(ranked)
        scenario_results.append(
            BenchmarkScenarioResult(
                name=name,
                description=description,
                rows=ranked,
                metrics=metrics,
            )
        )
        all_rows.extend(ranked)

    overall = calculate_benchmark_metrics(
        sorted(
            all_rows,
            key=lambda row: (
                -float(row.get("qualityScore") or 0.0),
                str(row.get("_benchmarkId") or ""),
            ),
        )
    )
    return BenchmarkReport(
        scenarios=tuple(scenario_results),
        metrics=overall,
    )


def calculate_benchmark_metrics(
    rows: Iterable[dict[str, Any]],
) -> BenchmarkMetrics:
    ranked = list(rows)
    grades = [
        _clamp_grade(row.get("_benchmarkRelevanceGrade"))
        for row in ranked
    ]
    useful = [grade >= 1 for grade in grades]

    precision_top = useful[:10]
    precision_at_10 = (
        sum(precision_top) / len(precision_top)
        if precision_top
        else 0.0
    )

    useful_total = sum(useful)
    recall_top = sum(useful[:100])
    recall_at_100 = (
        recall_top / useful_total
        if useful_total
        else 1.0
    )

    mrr = 0.0
    for index, grade in enumerate(grades, start=1):
        if grade >= 2:
            mrr = 1.0 / index
            break

    ndcg_at_20 = _ndcg(grades[:20])

    useful_pivots = 0
    useful_pivots_found = 0
    false_pivots = 0
    predicted_pivots = 0
    persist_expected = 0
    persist_found = 0
    false_persist = 0
    missed_by_legacy_visibility = 0
    missed_by_legacy_pivot = 0

    for row, grade in zip(ranked, grades):
        should_explore = bool(row.get("_benchmarkShouldExplore"))
        should_persist = bool(row.get("_benchmarkShouldPersist"))
        predicted_explore = bool(row.get("qualityWouldExplore"))
        predicted_persist = bool(row.get("qualityWouldPersist"))

        if should_explore:
            useful_pivots += 1
            if predicted_explore:
                useful_pivots_found += 1
        if predicted_explore:
            predicted_pivots += 1
            if not should_explore:
                false_pivots += 1

        if should_persist:
            persist_expected += 1
            if predicted_persist:
                persist_found += 1
        elif predicted_persist:
            false_persist += 1

        if grade >= 1 and not bool(row.get("qualityLegacyVisible")):
            missed_by_legacy_visibility += 1
        if should_explore and not bool(row.get("qualityLegacyPivotAllowed")):
            missed_by_legacy_pivot += 1

    false_pivot_rate = (
        false_pivots / predicted_pivots
        if predicted_pivots
        else 0.0
    )

    return BenchmarkMetrics(
        observations=len(ranked),
        useful_observations=useful_total,
        precision_at_10=precision_at_10,
        recall_at_100=recall_at_100,
        mrr=mrr,
        ndcg_at_20=ndcg_at_20,
        useful_pivots=useful_pivots,
        useful_pivots_found=useful_pivots_found,
        false_pivots=false_pivots,
        predicted_pivots=predicted_pivots,
        false_pivot_rate=false_pivot_rate,
        persist_expected=persist_expected,
        persist_found=persist_found,
        false_persist=false_persist,
        missed_by_legacy_visibility=missed_by_legacy_visibility,
        missed_by_legacy_pivot=missed_by_legacy_pivot,
    )


def evaluate_gate(
    report: BenchmarkReport,
    thresholds: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    thresholds = dict(thresholds or {})
    metrics = report.metrics

    minimums = {
        "precisionAt10": float(thresholds.get("precisionAt10", 0.60)),
        "recallAt100": float(thresholds.get("recallAt100", 0.90)),
        "mrr": float(thresholds.get("mrr", 0.50)),
        "ndcgAt20": float(thresholds.get("ndcgAt20", 0.65)),
        "pivotRecall": float(thresholds.get("pivotRecall", 0.50)),
        "persistRecall": float(thresholds.get("persistRecall", 0.50)),
    }
    maximums = {
        "falsePivotRate": float(
            thresholds.get("falsePivotRate", 0.35)
        ),
        "falsePersist": int(thresholds.get("falsePersist", 1)),
    }

    pivot_recall = (
        metrics.useful_pivots_found / metrics.useful_pivots
        if metrics.useful_pivots
        else 1.0
    )
    persist_recall = (
        metrics.persist_found / metrics.persist_expected
        if metrics.persist_expected
        else 1.0
    )

    actual = {
        "precisionAt10": metrics.precision_at_10,
        "recallAt100": metrics.recall_at_100,
        "mrr": metrics.mrr,
        "ndcgAt20": metrics.ndcg_at_20,
        "pivotRecall": pivot_recall,
        "persistRecall": persist_recall,
        "falsePivotRate": metrics.false_pivot_rate,
        "falsePersist": metrics.false_persist,
    }

    failures: list[str] = []
    for name, threshold in minimums.items():
        if actual[name] < threshold:
            failures.append(
                f"{name}={actual[name]:.4f} < minimum {threshold:.4f}"
            )
    for name, threshold in maximums.items():
        if actual[name] > threshold:
            failures.append(
                f"{name}={actual[name]:.4f} > maximum {float(threshold):.4f}"
            )
    return not failures, failures


def _ndcg(grades: list[int]) -> float:
    if not grades:
        return 0.0

    dcg = 0.0
    for index, grade in enumerate(grades, start=1):
        gain = (2 ** grade) - 1
        dcg += gain / math.log2(index + 1)

    ideal = sorted(grades, reverse=True)
    idcg = 0.0
    for index, grade in enumerate(ideal, start=1):
        gain = (2 ** grade) - 1
        idcg += gain / math.log2(index + 1)

    return dcg / idcg if idcg else 1.0


def _clamp_grade(value: Any) -> int:
    try:
        grade = int(value or 0)
    except (TypeError, ValueError):
        grade = 0
    return max(0, min(3, grade))
