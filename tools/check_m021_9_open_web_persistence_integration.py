from __future__ import annotations

import inspect

from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentService,
)
from app.osint.capabilities import DiscoveryGoal
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)


def main() -> int:
    print("=" * 72)
    print(
        "OSINTXZ M021.9 OPEN-WEB PERSISTENCE INTEGRATION AUDIT"
    )
    print("=" * 72)

    source = inspect.getsource(
        OpenWebEnrichmentService
    )

    checks = [
        (
            "DiscoveryGoal.OPEN_WEB_DISCOVERY exists",
            hasattr(
                DiscoveryGoal,
                "OPEN_WEB_DISCOVERY",
            ),
        ),
        (
            "generic persist_findings exists",
            hasattr(
                OsintFindingPersistenceService,
                "persist_findings",
            ),
        ),
        (
            "integration uses discovery service",
            "discovery_service.discover"
            in source,
        ),
        (
            "integration uses extraction bridge",
            "extraction_bridge.extract_documents"
            in source,
        ),
        (
            "integration uses existing persistence service",
            "persistence_service.persist_findings"
            in source,
        ),
        (
            "no relationship service dependency",
            "relationship_service"
            not in source,
        ),
        (
            "no recursive service dependency",
            "recursive_service"
            not in source,
        ),
    ]

    failed = False

    for label, ok in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{label}"
        )
        failed = failed or not ok

    print("\nPolicy:")
    print("- One persistence implementation remains authoritative.")
    print("- Provider evidence is stored independently by provider.")
    print("- Entity Resolution may converge identifiers across providers.")
    print("- Open-Web findings remain leads; no ownership inferred.")
    print("- No recursion or commit inside M021.9 service.")
    print("- No real network provider is introduced.")
    print("- No DB migration.")

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
