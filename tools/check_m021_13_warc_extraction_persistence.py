from __future__ import annotations
import inspect

from app.application.open_web_enrichment_service import OpenWebEnrichmentService
from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.osint.open_web.content_hydration import CommonCrawlContentHydrator
from app.osint.finding_persistence import OsintFindingPersistenceService


def main():
    print("=" * 72)
    print("OSINTXZ M021.13 WARC -> EXTRACTION -> PERSISTENCE AUDIT")
    print("=" * 72)

    s = inspect.getsource(OpenWebEnrichmentService)
    b = inspect.getsource(OpenWebIdentifierExtractionBridge)
    h = inspect.getsource(CommonCrawlContentHydrator)
    p = inspect.getsource(OsintFindingPersistenceService)

    checks = [
        ("hydration boundary present", "content_hydrator" in s),
        ("extraction uses hydrated documents", "extraction_documents" in s),
        ("UnifiedExtractionService extract_text retained", "extract_text(" in b),
        ("existing persistence retained", "persist_findings(" in s),
        ("hydration failure isolated", "except Exception" in h),
        ("lead-only semantics retained", '"lead_only": True' in b),
        ("ownership not asserted", '"verified_ownership": False' in b),
        ("generic persistence reuses core", "self._persist_finding(" in p),
        ("no recursive service", "recursive_service" not in s),
    ]

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print("\nPolicy:")
    print("- WARC content is hydrated before extraction.")
    print("- UnifiedExtractionService remains authoritative.")
    print("- OsintFindingPersistenceService remains authoritative.")
    print("- Findings remain leads, not ownership proof.")
    print("- No new recursion or DB migration.")
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
