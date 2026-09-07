from __future__ import annotations

import inspect

from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.services.unified_extraction_service import UnifiedExtractionService


def main() -> int:
    print("=" * 72)
    print("OSINTXZ M021.8 OPEN-WEB EXTRACTION BRIDGE AUDIT")
    print("=" * 72)

    failed = False

    extract_text = getattr(UnifiedExtractionService, "extract_text", None)
    checks = [
        ("UnifiedExtractionService.extract_text exists", callable(extract_text)),
        (
            "bridge depends on UnifiedExtractionService",
            "UnifiedExtractionService"
            in inspect.getsource(OpenWebIdentifierExtractionBridge),
        ),
        (
            "bridge has no persistence dependency",
            "persistence_service"
            not in inspect.getsource(OpenWebIdentifierExtractionBridge),
        ),
        (
            "bridge has no relationship dependency",
            "relationship_service"
            not in inspect.getsource(OpenWebIdentifierExtractionBridge),
        ),
        (
            "bridge has no recursive execution dependency",
            "recursive_service"
            not in inspect.getsource(OpenWebIdentifierExtractionBridge),
        ),
    ]

    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed = failed or not ok

    print("\nPolicy:")
    print("- OpenWebDocument URL/title/snippet/body use UnifiedExtractionService.")
    print("- No second regex or identifier normalizer is introduced.")
    print("- ExtractionCandidate -> existing OsintFinding contract.")
    print("- Open-Web findings are leads, not proof of identity/ownership.")
    print("- No persistence, relationship inference or recursion in this bridge.")
    print("- Per-document extraction failure is isolated.")
    print("- No network execution.")
    print("- No DB migration.")

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
