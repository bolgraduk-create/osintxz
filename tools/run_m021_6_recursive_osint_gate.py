"""
M021.6 recursive OSINT golden regression gate.

Runs only deterministic offline tests.
"""

from __future__ import annotations

import subprocess
import sys


TESTS = (
    "tests/test_osint_capability_catalog.py",
    "tests/test_osint_pivot_policy_router.py",
    "tests/test_osint_enrichment_execution.py",
    "tests/test_osint_finding_persistence.py",
    "tests/test_osint_enrichment_application_service.py",
    "tests/test_osint_recursive_enrichment.py",
    "tests/test_m021_4_service_container_integration.py",
    "tests/test_m021_5_service_container_integration.py",
    "tests/test_golden_osint_recursive_enrichment.py",
)


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.6 RECURSIVE OSINT GOLDEN REGRESSION GATE")
    print("=" * 72)
    print()
    print("Mode: OFFLINE / DETERMINISTIC")
    print("Network: DISABLED BY FIXTURE DESIGN")
    print("External CLI tools: NOT REQUIRED")
    print("Database: NOT REQUIRED")
    print()

    command = [
        sys.executable,
        "-m",
        "pytest",
        *TESTS,
        "-q",
    ]

    completed = subprocess.run(
        command,
        check=False,
    )

    print()
    print("=" * 72)
    if completed.returncode == 0:
        print("M021.6 RECURSIVE OSINT GOLDEN GATE: PASS")
        print("M021.0.1-M021.5 regression set: PASS")
        print("Recursive golden fixture: PASS")
        print("Persistence idempotency: PASS")
        print("Forbidden automatic connector guard: PASS")
    else:
        print("M021.6 RECURSIVE OSINT GOLDEN GATE: FAIL")
    print("=" * 72)

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
