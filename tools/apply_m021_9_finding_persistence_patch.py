"""Add generic persist_findings() entry point to M021.3 persistence service."""
from pathlib import Path

PATH = Path("app/osint/finding_persistence.py")

METHOD = '\n    def persist_findings(\n        self,\n        *,\n        case_id: UUID,\n        target_type: OsintTargetType,\n        target_value: str,\n        goal: DiscoveryGoal,\n        connector: str,\n        capability_module: str,\n        findings: list[OsintFinding] | tuple[OsintFinding, ...],\n        parent_entity_id: UUID | None = None,\n    ) -> OsintPersistenceResult:\n        """Persist standard OsintFinding objects through the M021.3 path.\n\n        This generic entry point is used by non-connector producers such as\n        Open-Web extraction. It reuses _persist_finding(), so provenance and\n        idempotency remain identical to connector execution persistence.\n        """\n        result = OsintPersistenceResult(\n            case_id=case_id,\n            target_type=target_type,\n            target_value=target_value,\n            goal=goal,\n        )\n\n        for index, finding in enumerate(findings):\n            if not self._is_persistable_finding(finding):\n                result.skipped_findings += 1\n                continue\n\n            result.persisted.append(\n                self._persist_finding(\n                    case_id=case_id,\n                    target_type=target_type,\n                    target_value=target_value,\n                    goal=goal,\n                    connector=connector,\n                    capability_module=capability_module,\n                    finding=finding,\n                    finding_index=index,\n                    parent_entity_id=parent_entity_id,\n                )\n            )\n\n        return result\n\n'


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    text = PATH.read_text(encoding="utf-8")

    if "def persist_findings(" in text:
        print("[PASS] M021.9 persist_findings already present.")
        return 0

    anchor = "    def _persist_finding(\n"
    if anchor not in text:
        print("[FAIL] M021.3 _persist_finding anchor not found.")
        return 1

    text = text.replace(
        anchor,
        METHOD + anchor,
        1,
    )

    compile(text, str(PATH), "exec")

    backup = PATH.with_suffix(".py.m021_9_backup")
    if not backup.exists():
        backup.write_text(
            PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    PATH.write_text(
        text,
        encoding="utf-8",
    )

    print("[PASS] M021.9 generic persistence entry point applied.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
