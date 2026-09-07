from __future__ import annotations

from pathlib import Path


REVISION = '"""add OSINT to source_type enum\n\nRevision ID: 20260902_2015\nRevises: 20260830_1006\nCreate Date: 2026-09-02\n"""\n\nfrom __future__ import annotations\n\nfrom alembic import op\n\n\nrevision = "20260902_2015"\ndown_revision = "20260830_1006"\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    # PostgreSQL enum additions should be committed before the value is used\n    # by later application transactions. Keep the enum DDL isolated.\n    with op.get_context().autocommit_block():\n        op.execute(\n            """\n            ALTER TYPE source_type\n            ADD VALUE IF NOT EXISTS \'OSINT\' BEFORE \'OTHER\'\n            """\n        )\n\n\ndef downgrade() -> None:\n    # PostgreSQL cannot remove a single enum label safely with ALTER TYPE.\n    # A downgrade after OSINT data exists would require rebuilding the enum\n    # and deciding what to do with persisted OSINT rows, which is data-policy\n    # sensitive. Fail explicitly instead of silently corrupting provenance.\n    raise RuntimeError(\n        "Downgrade of revision 20260902_2015 is intentionally blocked: "\n        "removing source_type.OSINT requires an explicit data migration."\n    )\n'
FILENAME = "20260902_2015_add_osint_to_source_type.py"


def find_versions_dir() -> Path | None:
    candidates = (
        Path("alembic/versions"),
        Path("migrations/versions"),
    )
    for path in candidates:
        if path.is_dir():
            return path
    return None


def main() -> int:
    versions = find_versions_dir()
    if versions is None:
        print("[FAIL] Alembic versions directory not found.")
        return 1

    target = versions / FILENAME

    if target.exists():
        current = target.read_text(encoding="utf-8")
        if 'revision = "20260902_2015"' in current:
            print(f"[PASS] Migration already exists: {target}")
            return 0
        print(f"[FAIL] Conflicting migration file exists: {target}")
        return 1

    # Guard against duplicate revision id elsewhere.
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'revision = "20260902_2015"' in text:
            print(f"[FAIL] Revision id already exists in {path}")
            return 1

    compile(REVISION, str(target), "exec")
    target.write_text(REVISION, encoding="utf-8")

    print(f"[PASS] Created Alembic migration: {target}")
    print("[PASS] down_revision = 20260830_1006")
    print("[PASS] Adds PostgreSQL source_type label OSINT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
