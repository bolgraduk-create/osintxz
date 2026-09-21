from __future__ import annotations

import json
from pathlib import Path
import sys

from app.application.search_quality_benchmark import (
    evaluate_gate,
    load_benchmark_fixture,
    run_search_quality_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "search_quality_benchmark" / "scenarios.json"


def main() -> int:
    fixture = load_benchmark_fixture(FIXTURE)
    report = run_search_quality_benchmark(fixture)
    passed, failures = evaluate_gate(
        report,
        fixture.get("thresholds") if isinstance(fixture, dict) else None,
    )

    metrics = report.metrics.to_dict()
    print("R13.26b Search Quality Benchmark")
    print("=" * 36)
    for key, value in metrics.items():
        print(f"{key}: {value}")

    print()
    for scenario in report.scenarios:
        print(f"[{scenario.name}]")
        for key, value in scenario.metrics.to_dict().items():
            print(f"  {key}: {value}")

    output_path = ROOT / "storage" / "exports" / "search_quality_benchmark_latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print(f"Report: {output_path}")

    if passed:
        print("GATE: PASS")
        return 0

    print("GATE: FAIL")
    for failure in failures:
        print(f" - {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
