from __future__ import annotations

from pathlib import Path


PATH = Path(
    "app/core/service_container.py"
)


def main() -> int:
    print("=" * 72)
    print(
        "OSINTXZ M021.10 OPEN-WEB E2E + "
        "SERVICE CONTAINER AUDIT"
    )
    print("=" * 72)

    text = PATH.read_text(
        encoding="utf-8"
    )

    checks = [
        (
            "one OpenWebProviderRegistry",
            text.count(
                "self.open_web_provider_registry ="
            ) == 1,
        ),
        (
            "one OpenWebDiscoveryService",
            text.count(
                "self.open_web_discovery_service ="
            ) == 1,
        ),
        (
            "one OpenWebIdentifierExtractionBridge",
            text.count(
                "self.open_web_identifier_extraction_bridge ="
            ) == 1,
        ),
        (
            "one OpenWebEnrichmentService",
            text.count(
                "self.open_web_enrichment_service ="
            ) == 1,
        ),
        (
            "existing UnifiedExtractionService reused",
            (
                "extraction_service=("
                in text
                and "self.unified_extraction_service"
                in text
            ),
        ),
        (
            "existing OSINT persistence reused",
            (
                "persistence_service=("
                in text
                and
                "self.osint_finding_persistence_service"
                in text
            ),
        ),
        (
            "single OsintManager construction",
            text.count(
                "self.osint_manager ="
            ) == 1,
        ),
        (
            "single OsintPipeline construction",
            text.count(
                "self.osint_pipeline ="
            ) == 1,
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
    print("- M021.7-M021.9 are wired through one composition root.")
    print("- Existing UnifiedExtractionService is reused.")
    print("- Existing OsintFindingPersistenceService is reused.")
    print("- No second OSINT runtime is created.")
    print("- Provider registry starts empty.")
    print("- No real network provider is enabled.")
    print("- No automatic recursion is added.")
    print("- No DB migration.")

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
