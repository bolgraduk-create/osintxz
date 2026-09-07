from __future__ import annotations

import inspect
from pathlib import Path

from app.application.open_web_recursive_pivot_service import OpenWebRecursivePivotService
from app.application.osint_recursive_enrichment_service import OsintRecursiveEnrichmentService
from app.osint.pivot_candidates import OsintPivotCandidatePolicy


def main():
    print("=" * 72)
    print("OSINTXZ M021.14 OPEN-WEB PERSISTED ENTITY -> RECURSIVE PIVOT AUDIT")
    print("=" * 72)

    bridge = inspect.getsource(OpenWebRecursivePivotService)
    recursive = inspect.getsource(OsintRecursiveEnrichmentService.enrich)
    policy = inspect.getsource(OsintPivotCandidatePolicy)
    container = Path("app/core/service_container.py").read_text(encoding="utf-8")

    checks = [
        ("persisted-entity generic candidate path", "from_persistence_results" in policy),
        ("Open-Web bridge uses persistence candidates", "from_persistence_results" in bridge),
        ("raw extraction findings are not seeds", ".extraction.findings" not in bridge),
        ("raw document text is not a seed source", ".text" not in bridge),
        ("existing recursive service reused", "recursive_service.enrich" in bridge),
        ("seed depth supported", "seed_depth: int = 0" in recursive),
        ("depth is propagated", "seed_depth=next_depth" in bridge),
        ("one recursive engine retained", container.count("self.osint_recursive_enrichment_service =") == 1),
        ("one Open-Web recursive bridge", container.count("self.open_web_recursive_pivot_service =") == 1),
        ("single OsintPipeline retained", container.count("self.osint_pipeline =") == 1),
    ]

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print("\nPolicy:")
    print("- Only persisted Entity objects may become recursive seeds.")
    print("- Raw WARC text and raw OsintFinding objects never seed recursion.")
    print("- Existing EntityType whitelist remains authoritative.")
    print("- Existing M021.5 BFS/routing/limits/dedup remain authoritative.")
    print("- Open-Web depth is continued, never reset to zero.")
    print("- No second recursion engine.")
    print("- No DB migration.")
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
