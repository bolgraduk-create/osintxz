"""
Apply M021.4 ServiceContainer wiring to the current project.

The script is intentionally strict and idempotent:
- it patches only app/core/service_container.py
- it refuses to continue if expected anchors are missing
- it does not overwrite a file that already contains the complete wiring
"""

from __future__ import annotations

from pathlib import Path


PATH = Path("app/core/service_container.py")


OSINT_IMPORTS = """from app.osint.enrichment_execution import (
    OsintEnrichmentExecutionService,
)

from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)

"""

APPLICATION_IMPORT = """from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
)

"""

CONSTRUCTION = """        self.osint_enrichment_execution_service = (
            OsintEnrichmentExecutionService(
                pipeline=(
                    self.osint_pipeline
                ),
            )
        )

        self.osint_finding_persistence_service = (
            OsintFindingPersistenceService(
                source_service=(
                    self.source_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                entity_service=(
                    self.entity_service
                ),
                evidence_link_service=(
                    self.evidence_link_service
                ),
            )
        )

        self.osint_enrichment_service = (
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


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    text = PATH.read_text(encoding="utf-8")

    already_complete = all(
        token in text
        for token in (
            "OsintEnrichmentExecutionService",
            "OsintFindingPersistenceService",
            "OsintEnrichmentService",
            "self.osint_enrichment_execution_service",
            "self.osint_finding_persistence_service",
            "self.osint_enrichment_service",
        )
    )
    if already_complete:
        print("[PASS] M021.4 ServiceContainer wiring already applied.")
        return 0

    pipeline_import_anchor = """from app.osint.pipeline import (
    OsintPipeline,
)

"""
    if pipeline_import_anchor not in text:
        print("[FAIL] Could not locate OsintPipeline import anchor.")
        return 1

    if "from app.osint.enrichment_execution import" not in text:
        text = text.replace(
            pipeline_import_anchor,
            pipeline_import_anchor + OSINT_IMPORTS,
            1,
        )

    workspace_import_anchor = """from app.application.osint_workspace_service import (
    OsintWorkspaceService,
)

"""
    if workspace_import_anchor not in text:
        print("[FAIL] Could not locate OsintWorkspaceService import anchor.")
        return 1

    if "from app.application.osint_enrichment_service import" not in text:
        text = text.replace(
            workspace_import_anchor,
            workspace_import_anchor + APPLICATION_IMPORT,
            1,
        )

    target_builder_block = """        self.osint_target_builder = (
            OsintTargetBuilder()
        )

"""
    if target_builder_block not in text:
        print("[FAIL] Could not locate osint_target_builder construction anchor.")
        return 1

    if "self.osint_enrichment_service = (" not in text:
        text = text.replace(
            target_builder_block,
            target_builder_block + CONSTRUCTION,
            1,
        )

    # Compile before touching the actual file.
    compile(text, str(PATH), "exec")

    backup = PATH.with_suffix(".py.m021_4_backup")
    if not backup.exists():
        backup.write_text(
            PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    PATH.write_text(text, encoding="utf-8")

    print("[PASS] M021.4 ServiceContainer wiring applied.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
