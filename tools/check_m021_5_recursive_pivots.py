from __future__ import annotations

import ast
from pathlib import Path

from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.pivot_candidates import OsintPivotCandidatePolicy


CONTAINER = Path(
    "app/core/service_container.py"
)


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.5 CONTROLLED RECURSIVE PIVOT AUDIT")
    print("=" * 72)

    policy = OsintPivotCandidatePolicy()

    expected = {
        EntityType.USERNAME: OsintTargetType.USERNAME,
        EntityType.EMAIL: OsintTargetType.EMAIL,
        EntityType.PHONE: OsintTargetType.PHONE,
        EntityType.DOMAIN: OsintTargetType.DOMAIN,
        EntityType.URL: OsintTargetType.URL,
        EntityType.IP: OsintTargetType.IP,
    }

    failed = False

    for entity_type, target_type in expected.items():
        actual = policy.target_type_for_entity(
            entity_type
        )
        ok = actual is target_type
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{entity_type.value} -> "
            f"{target_type.value}"
        )
        failed = failed or not ok

    blocked = (
        EntityType.ACCOUNT,
        EntityType.PERSON,
        EntityType.ORGANIZATION,
        EntityType.LOCATION,
    )

    for entity_type in blocked:
        ok = (
            policy.target_type_for_entity(
                entity_type
            )
            is None
        )
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{entity_type.value} blocked from automatic recursion"
        )
        failed = failed or not ok

    if not CONTAINER.is_file():
        print(
            "[FAIL] service_container.py missing"
        )
        return 1

    source = CONTAINER.read_text(
        encoding="utf-8"
    )
    ast.parse(source)

    required = (
        "from app.application.osint_recursive_enrichment_service import",
        "self.osint_recursive_enrichment_service",
        "enrichment_service=(\n                    self.osint_enrichment_service",
    )

    for token in required:
        ok = token in source
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"ServiceContainer token: {token.splitlines()[0]}"
        )
        failed = failed or not ok

    print("\nPolicy:")
    print("- BFS recursive traversal.")
    print("- Candidates come only from persisted Entity objects.")
    print("- max_depth enforced.")
    print("- existing visited-pivot policy remains authoritative.")
    print("- max_new_entities stops future recursive expansion.")
    print("- active/credentialed connector policy remains unchanged.")
    print("- no transaction commit inside recursive service.")
    print("- no DB migration.")

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
