from __future__ import annotations

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType
from app.osint.finding_persistence import OsintFindingPersistenceService


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.3 FINDINGS PERSISTENCE + PROVENANCE AUDIT")
    print("=" * 72)

    checks = [
        ("SourceType.OSINT exists", SourceType.OSINT.value == "osint"),
        ("EvidenceType.LINK exists", EvidenceType.LINK.value == "link"),
        ("EvidenceType.PHONE exists", EvidenceType.PHONE.value == "phone"),
        ("EvidenceType.EMAIL exists", EvidenceType.EMAIL.value == "email"),
        ("EvidenceType.USERNAME exists", EvidenceType.USERNAME.value == "username"),
        ("EntityType.PHONE exists", EntityType.PHONE.value == "phone"),
        ("EntityType.EMAIL exists", EntityType.EMAIL.value == "email"),
        ("EntityType.USERNAME exists", EntityType.USERNAME.value == "username"),
        ("EntityType.DOMAIN exists", EntityType.DOMAIN.value == "domain"),
        ("EntityType.URL exists", EntityType.URL.value == "url"),
        ("EntityType.IP exists", EntityType.IP.value == "ip"),
        (
            "Persistence service has no relationship_service dependency",
            "relationship_service"
            not in OsintFindingPersistenceService.__init__.__annotations__,
        ),
    ]

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed = failed or not ok

    print("\nPolicy:")
    print("- OSINT findings reuse existing Source/Evidence/Entity models.")
    print("- EvidenceEntity links carry pivot provenance.")
    print("- No ownership/belongs-to relationship is inferred from discovery alone.")
    print("- Repeat persistence uses deterministic source/evidence keys.")
    print("- No schema migration is required.")

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
