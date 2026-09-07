"""
Apply M021.5 recursive enrichment wiring to ServiceContainer.

Strict and idempotent. Creates a backup before modification.
"""

from __future__ import annotations

from pathlib import Path


PATH = Path("app/core/service_container.py")


IMPORT = """from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
)

"""

CONSTRUCTION = """        self.osint_recursive_enrichment_service = (
            OsintRecursiveEnrichmentService(
                enrichment_service=(
                    self.osint_enrichment_service
                ),
            )
        )

"""


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    text = PATH.read_text(encoding="utf-8")

    if (
        "OsintRecursiveEnrichmentService"
        in text
        and "self.osint_recursive_enrichment_service"
        in text
    ):
        print(
            "[PASS] M021.5 ServiceContainer wiring already applied."
        )
        return 0

    import_anchor = """from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
)

"""
    if import_anchor not in text:
        print(
            "[FAIL] M021.4 application import anchor not found."
        )
        return 1

    text = text.replace(
        import_anchor,
        import_anchor + IMPORT,
        1,
    )

    construction_anchor = """        self.osint_enrichment_service = (
            OsintEnrichmentService(
                execution_service=(
                    self.osint_enrichment_execution_service
                ),
                persistence_service=(
                    self.osint_finding_persistence_service
                ),
            )
        )

"""
    if construction_anchor not in text:
        print(
            "[FAIL] M021.4 enrichment construction anchor not found."
        )
        return 1

    text = text.replace(
        construction_anchor,
        construction_anchor + CONSTRUCTION,
        1,
    )

    compile(text, str(PATH), "exec")

    backup = PATH.with_suffix(
        ".py.m021_5_backup"
    )
    if not backup.exists():
        backup.write_text(
            PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    PATH.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "[PASS] M021.5 ServiceContainer wiring applied."
    )
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
