from __future__ import annotations

from pathlib import Path
import json


ROOT = Path("tests/fixtures/golden_osint_recursive")


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.6 GOLDEN FIXTURE CONTRACT AUDIT")
    print("=" * 72)

    required = [
        Path("tests/golden_osint_recursive_runtime.py"),
        Path("tests/test_golden_osint_recursive_enrichment.py"),
        ROOT / "scenario.json",
        ROOT / "expected.json",
        Path("tools/run_m021_6_recursive_osint_gate.py"),
    ]

    failed = False

    for path in required:
        ok = path.is_file()
        print(
            f"[{'PASS' if ok else 'FAIL'}] {path}"
        )
        failed = failed or not ok

    if failed:
        print("\nRESULT: FAIL")
        return 1

    scenario = json.loads(
        (ROOT / "scenario.json").read_text(
            encoding="utf-8"
        )
    )
    expected = json.loads(
        (ROOT / "expected.json").read_text(
            encoding="utf-8"
        )
    )

    checks = [
        (
            "single deterministic USERNAME seed",
            len(scenario["seeds"]) == 1
            and scenario["seeds"][0]["target_type"] == "username",
        ),
        (
            "fixture has no network configuration",
            "network" not in scenario
            and "api_key" not in scenario,
        ),
        (
            "expected recursive depth reaches 2",
            expected["targets_processed"] >= 3,
        ),
        (
            "forbidden connectors absent from expected execution",
            not {
                "Nmap",
                "GHunt",
                "Nuclei",
                "Naabu",
                "FFUF",
                "Feroxbuster",
            }
            & set(expected["executed_connectors"]),
        ),
        (
            "expected persisted provenance objects exist",
            bool(expected["sources"])
            and bool(expected["evidences"])
            and bool(expected["entities"]),
        ),
    ]

    for label, ok in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] {label}"
        )
        failed = failed or not ok

    print("\nPolicy:")
    print("- Real M021 orchestration services are exercised.")
    print("- Connector behavior is deterministic and offline.")
    print("- Persistence uses in-memory repositories.")
    print("- ACCOUNT is persisted but not recursively pivoted.")
    print("- Active/credentialed tools are present as traps but must never execute.")
    print("- Full rerun must be persistence-idempotent.")
    print("- No DB migration.")

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
