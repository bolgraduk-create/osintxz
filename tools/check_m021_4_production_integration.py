from __future__ import annotations

import ast
from pathlib import Path


CONTAINER = Path("app/core/service_container.py")


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.4 PRODUCTION INTEGRATION AUDIT")
    print("=" * 72)

    if not CONTAINER.is_file():
        print("[FAIL] app/core/service_container.py missing")
        return 1

    source = CONTAINER.read_text(encoding="utf-8")
    ast.parse(source)

    required = {
        "execution import": (
            "from app.osint.enrichment_execution import"
        ),
        "persistence import": (
            "from app.osint.finding_persistence import"
        ),
        "application import": (
            "from app.application.osint_enrichment_service import"
        ),
        "execution singleton": (
            "self.osint_enrichment_execution_service"
        ),
        "persistence singleton": (
            "self.osint_finding_persistence_service"
        ),
        "application singleton": (
            "self.osint_enrichment_service"
        ),
        "shared pipeline": (
            "pipeline=(\n                    self.osint_pipeline"
        ),
        "shared source service": (
            "source_service=(\n                    self.source_service"
        ),
        "shared evidence service": (
            "evidence_service=(\n                    self.evidence_service"
        ),
        "shared entity service": (
            "entity_service=(\n                    self.entity_service"
        ),
        "shared evidence link service": (
            "evidence_link_service=(\n                    self.evidence_link_service"
        ),
    }

    failed = False
    for label, token in required.items():
        ok = token in source
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed = failed or not ok

    # Guard against accidentally introducing a second OSINT manager.
    manager_constructions = source.count("OsintManager()")
    pipeline_constructions = source.count("OsintPipeline(")

    print(
        f"[{'PASS' if manager_constructions == 1 else 'FAIL'}] "
        f"single OsintManager construction ({manager_constructions})"
    )
    print(
        f"[{'PASS' if pipeline_constructions == 1 else 'FAIL'}] "
        f"single OsintPipeline construction ({pipeline_constructions})"
    )
    failed = failed or manager_constructions != 1
    failed = failed or pipeline_constructions != 1

    print("\nPolicy:")
    print("- Manual OSINT Workspace remains intact.")
    print("- Investigation enrichment reuses the same OsintPipeline.")
    print("- No recursive auto-pivot is enabled yet.")
    print("- No service commits the transaction internally.")
    print("- No database migration is required.")

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
