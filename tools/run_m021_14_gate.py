from __future__ import annotations

import subprocess
import sys

TESTS = [
    "tests/test_m021_14_open_web_recursive_pivots.py",
    "tests/test_m021_14_seed_depth.py",
    "tests/test_m021_14_service_container.py",
    "tests/test_osint_recursive_enrichment.py",
    "tests/test_m021_5_service_container_integration.py",
    "tests/test_golden_osint_recursive_enrichment.py",
    "tests/test_m021_13_open_web_warc_extraction_persistence_e2e.py",
]


def main():
    print("=" * 72)
    print("M021.14 OPEN-WEB -> CONTROLLED RECURSIVE PIVOT GATE")
    print("=" * 72)

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q"],
        check=False,
    )

    if completed.returncode != 0:
        print("\nM021.14 GATE: FAIL")
        return completed.returncode

    print("\nM021.14 GATE: PASS")
    print("Persisted Entity-only seeds: PASS")
    print("Entity whitelist: PASS")
    print("Depth continuation: PASS")
    print("Existing M021.5 recursion reused: PASS")
    print("M021.5 golden regression: PASS")
    print("M021.13 WARC regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
