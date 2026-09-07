"""Stage 23 deterministic integration gate for the current Investigation foundation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TESTS = (
    "tests/test_unified_extraction_service.py",
    "tests/test_phone_extraction_hardening.py",
    "tests/test_bank_card_extraction_hardening.py",
    "tests/test_extraction_evidence_provenance.py",
    "tests/test_extraction_entity_resolution_integration.py",
    "tests/test_telegram_identifier_e2e.py",
    "tests/test_investigation_engine_contract_audit.py",
    "tests/test_structured_search_retriever.py",
    "tests/test_retrieve_fuse_rank_resolve_integration.py",
    "tests/test_search_confidence_explainability.py",
    "tests/test_golden_investigation_fixture.py",
)


def _run(label: str, command: list[str]) -> int:
    print(f"\n=== {label} ===", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def main() -> int:
    print("======================================")
    print("OSINTXZ STAGE 23 INTEGRATION GATE")
    print("======================================")

    missing = [path for path in TESTS if not (PROJECT_ROOT / path).is_file()]
    if missing:
        print("RESULT: FAIL")
        print("Missing gate files:")
        for path in missing:
            print(f"  - {path}")
        return 2

    contract_code = _run(
        "INVESTIGATION CONTRACT AUDIT",
        [sys.executable, "tools/check_investigation_contracts.py"],
    )
    if contract_code != 0:
        print("\nRESULT: FAIL (contract audit)")
        return contract_code

    test_code = _run(
        "STAGE 23 REGRESSION + GOLDEN FIXTURE",
        [sys.executable, "-m", "pytest", *TESTS, "-q"],
    )
    if test_code != 0:
        print("\nRESULT: FAIL (pytest gate)")
        return test_code

    print("\n======================================")
    print("STAGE 23 INTEGRATION GATE: PASS")
    print("Golden investigation fixture: PASS")
    print("Contract audit: PASS")
    print("Regression manifest: PASS")
    print("======================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
