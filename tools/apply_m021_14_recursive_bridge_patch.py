from __future__ import annotations

from pathlib import Path

POLICY = Path("app/osint/pivot_candidates.py")
RECURSIVE = Path("app/application/osint_recursive_enrichment_service.py")
CONTAINER = Path("app/core/service_container.py")

GENERIC_METHOD = '\n    def from_persistence_results(\n        self,\n        persistence_results,\n        *,\n        next_depth: int,\n        discovered_from_entity_id: UUID | None = None,\n    ) -> tuple[RecursivePivotCandidate, ...]:\n        """Build recursive candidates only from persisted Entity objects."""\n        candidates: list[RecursivePivotCandidate] = []\n        seen: set[tuple[UUID, OsintTargetType, str]] = set()\n\n        for persistence_result in persistence_results:\n            for persisted_finding in persistence_result.persisted:\n                evidence_id = getattr(\n                    persisted_finding.evidence,\n                    "id",\n                    None,\n                )\n\n                for entity in persisted_finding.entities:\n                    candidate = self.from_entity(\n                        entity,\n                        depth=next_depth,\n                        discovered_from_entity_id=discovered_from_entity_id,\n                        evidence_id=evidence_id,\n                    )\n\n                    if candidate is None:\n                        continue\n\n                    key = (\n                        candidate.entity_id,\n                        candidate.target_type,\n                        candidate.value.strip().casefold(),\n                    )\n\n                    if key in seen:\n                        continue\n\n                    seen.add(key)\n                    candidates.append(candidate)\n\n        return tuple(candidates)\n\n'


def patch_policy():
    original = POLICY.read_text(encoding="utf-8")
    text = original

    if "def from_persistence_results(" not in text:
        anchor = "    def from_enrichment_result(\n"
        if anchor not in text:
            return False, "from_enrichment_result anchor not found."
        text = text.replace(anchor, GENERIC_METHOD + anchor, 1)

    start = text.find("    def from_enrichment_result(")
    end = text.find("    def from_entity(", start)

    if start < 0 or end < 0:
        return False, "from_enrichment_result block not found."

    block = text[start:end]
    if ".from_persistence_results(" not in block:
        new_block = (
            "    def from_enrichment_result(\n"
            "        self,\n"
            "        result: OsintTargetEnrichmentResult,\n"
            "        *,\n"
            "        next_depth: int,\n"
            "    ) -> tuple[RecursivePivotCandidate, ...]:\n"
            "        return self.from_persistence_results(\n"
            "            result.persistence,\n"
            "            next_depth=next_depth,\n"
            "            discovered_from_entity_id=result.parent_entity_id,\n"
            "        )\n\n"
        )
        text = text[:start] + new_block + text[end:]

    compile(text, str(POLICY), "exec")
    backup = POLICY.with_suffix(".py.m021_14_backup")
    if text != original and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    POLICY.write_text(text, encoding="utf-8")
    return True, str(backup)


def patch_recursive():
    original = RECURSIVE.read_text(encoding="utf-8")
    text = original

    if "seed_depth: int = 0," not in text:
        anchor = (
            "        state: PivotTraversalState | None = None,\n"
            "        timeout: int = 300,\n"
        )
        if anchor not in text:
            return False, "recursive enrich signature anchor not found."
        text = text.replace(
            anchor,
            (
                "        state: PivotTraversalState | None = None,\n"
                "        seed_depth: int = 0,\n"
                "        timeout: int = 300,\n"
            ),
            1,
        )

    if "seed_depth must be >= 0" not in text:
        anchor = "        traversal_state = state or PivotTraversalState()\n"
        if anchor not in text:
            return False, "traversal_state anchor not found."
        text = text.replace(
            anchor,
            (
                "        if seed_depth < 0:\n"
                "            raise ValueError(\"seed_depth must be >= 0.\")\n"
                "\n"
                + anchor
            ),
            1,
        )

    seed_start = text.find("        for seed in seeds:")
    seed_end = text.find("        limits = (", seed_start)
    if seed_start < 0 or seed_end < 0:
        return False, "seed queue block not found."

    seed_block = text[seed_start:seed_end]
    if "seed_depth" not in seed_block:
        old = (
            "                    0,\n"
            "                )\n"
            "            )\n"
        )
        if old not in seed_block:
            return False, "root depth literal anchor not found."
        seed_block = seed_block.replace(
            old,
            (
                "                    seed_depth,\n"
                "                )\n"
                "            )\n"
            ),
            1,
        )
        text = text[:seed_start] + seed_block + text[seed_end:]

    compile(text, str(RECURSIVE), "exec")
    backup = RECURSIVE.with_suffix(".py.m021_14_backup")
    if text != original and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    RECURSIVE.write_text(text, encoding="utf-8")
    return True, str(backup)


def patch_container():
    original = CONTAINER.read_text(encoding="utf-8")
    text = original

    import_block = (
        "from app.application.open_web_recursive_pivot_service import (\n"
        "    OpenWebRecursivePivotService,\n"
        ")\n\n"
    )

    if "from app.application.open_web_recursive_pivot_service import" not in text:
        anchor = "class ServiceContainer:"
        if anchor not in text:
            return False, "ServiceContainer class anchor not found."
        text = text.replace(anchor, import_block + anchor, 1)

    if "self.open_web_recursive_pivot_service =" not in text:
        anchor = "        self.open_web_enrichment_service = (\n"
        start = text.find(anchor)
        if start < 0:
            return False, "OpenWebEnrichmentService wiring anchor not found."

        pos = start + len(anchor)
        depth = 1
        while pos < len(text):
            ch = text[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and ch == "\n":
                pos += 1
                break
            pos += 1

        wiring = (
            "\n        self.open_web_recursive_pivot_service = (\n"
            "            OpenWebRecursivePivotService(\n"
            "                recursive_service=(\n"
            "                    self.osint_recursive_enrichment_service\n"
            "                ),\n"
            "            )\n"
            "        )\n"
        )
        text = text[:pos] + wiring + text[pos:]

    checks = {
        "open web recursive pivot service": text.count("self.open_web_recursive_pivot_service =") == 1,
        "existing recursive service": text.count("self.osint_recursive_enrichment_service =") == 1,
        "single Open-Web enrichment": text.count("self.open_web_enrichment_service =") == 1,
        "single pipeline": text.count("self.osint_pipeline =") == 1,
    }

    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return False, "singleton guard failed: " + ", ".join(failed)

    compile(text, str(CONTAINER), "exec")
    backup = CONTAINER.with_suffix(".py.m021_14_backup")
    if text != original and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    CONTAINER.write_text(text, encoding="utf-8")
    return True, str(backup)


def main():
    for path in (POLICY, RECURSIVE, CONTAINER):
        if not path.is_file():
            print(f"[FAIL] Missing {path}")
            return 1

    ok, info = patch_policy()
    if not ok:
        print(f"[FAIL] Candidate policy: {info}")
        return 1
    print("[PASS] Generic persisted-entity candidate policy applied.")
    print(f"[INFO] Policy backup: {info}")

    ok, info = patch_recursive()
    if not ok:
        print(f"[FAIL] Recursive service: {info}")
        return 1
    print("[PASS] M021.5 seed_depth support applied.")
    print(f"[INFO] Recursive backup: {info}")

    ok, info = patch_container()
    if not ok:
        print(f"[FAIL] ServiceContainer: {info}")
        return 1
    print("[PASS] M021.14 Open-Web recursive pivot wiring applied.")
    print(f"[INFO] Container backup: {info}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
