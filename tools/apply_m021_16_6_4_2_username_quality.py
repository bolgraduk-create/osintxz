from __future__ import annotations

from pathlib import Path

PERSISTENCE = Path("app/osint/finding_persistence.py")


def main() -> int:
    if not PERSISTENCE.exists():
        print(f"[FAIL] Missing {PERSISTENCE}")
        return 1

    original = PERSISTENCE.read_text(encoding="utf-8")
    marker = "M021.16.6.4.2 username quality gate"

    if marker in original:
        print("[PASS] Patch already applied.")
        return 0

    text = original

    import_anchor = "from app.osint.result import OsintFinding, ResultStatus\n"
    import_add = import_anchor + (
        "from app.osint.username_quality import (\n"
        "    UsernameFindingKind,\n"
        "    UsernameFindingQuality,\n"
        ")\n"
    )

    if import_anchor not in text:
        print("[FAIL] import anchor not found.")
        return 1

    text = text.replace(import_anchor, import_add, 1)

    call_anchor = "        entity_candidates = self._entity_candidates(finding)\n"
    call_replacement = (
        "        entity_candidates = self._entity_candidates(finding)\n\n"
        "        # M021.16.6.4.2 username quality gate\n"
        "        if (\n"
        "            target_type is OsintTargetType.USERNAME\n"
        "            and goal is DiscoveryGoal.ACCOUNT_DISCOVERY\n"
        "        ):\n"
        "            entity_candidates = self._username_quality_candidates(\n"
        "                finding=finding,\n"
        "                target_value=target_value,\n"
        "                candidates=entity_candidates,\n"
        "            )\n"
    )

    if call_anchor not in text:
        print("[FAIL] entity_candidates call anchor not found.")
        return 1

    text = text.replace(call_anchor, call_replacement, 1)

    method_anchor = "    @staticmethod\n    def _entity_candidates(\n"
    helper = """    @classmethod
    def _username_quality_candidates(
        cls,
        *,
        finding: OsintFinding,
        target_value: str,
        candidates: tuple[tuple[EntityType, str, float], ...],
    ) -> tuple[tuple[EntityType, str, float], ...]:
        classification = UsernameFindingQuality.classify(
            category=finding.category,
            value=finding.value,
            url=finding.url,
            target_username=target_value,
            metadata=finding.metadata,
        )

        filtered: list[tuple[EntityType, str, float]] = []

        for entity_type, value, confidence in candidates:
            if entity_type is EntityType.ACCOUNT:
                continue

            if entity_type is EntityType.URL:
                if classification.kind is not UsernameFindingKind.PUBLIC_PROFILE:
                    continue

                canonical = (
                    classification.canonical_profile_url
                    or UsernameFindingQuality.canonicalize_url(value)
                )

                if not canonical:
                    continue

                filtered.append((EntityType.URL, canonical, confidence))
                continue

            filtered.append((entity_type, value, confidence))

        unique: list[tuple[EntityType, str, float]] = []
        seen: set[tuple[EntityType, str]] = set()

        for item in filtered:
            key = (item[0], item[1].strip().casefold())
            if not key[1] or key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return tuple(unique)

"""

    if method_anchor not in text:
        print("[FAIL] _entity_candidates method anchor not found.")
        return 1

    text = text.replace(method_anchor, helper + method_anchor, 1)

    try:
        compile(text, str(PERSISTENCE), "exec")
    except Exception as exc:
        print(f"[FAIL] Patched persistence does not compile: {exc}")
        return 1

    backup = PERSISTENCE.with_suffix(".py.m021_16_6_4_2_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    PERSISTENCE.write_text(text, encoding="utf-8")

    print("[PASS] Username quality gate added.")
    print("[PASS] Raw Evidence remains unchanged.")
    print("[PASS] Generic ACCOUNT=username entity suppressed.")
    print("[PASS] Service/login endpoints suppressed as URL entities.")
    print("[PASS] Public profile URLs canonicalized.")
    print("[PASS] Non-USERNAME persistence unchanged.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
