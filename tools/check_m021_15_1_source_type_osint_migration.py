from __future__ import annotations

from pathlib import Path
import re


def find_migration() -> Path | None:
    for base in (Path("alembic/versions"), Path("migrations/versions")):
        if not base.is_dir():
            continue
        for path in base.glob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if 'revision = "20260902_2015"' in text:
                return path
    return None


def main() -> int:
    path = find_migration()

    print("=" * 72)
    print("M021.15.1 SOURCE TYPE OSINT MIGRATION AUDIT")
    print("=" * 72)

    if path is None:
        print("[FAIL] Migration revision 20260902_2015 not found.")
        return 1

    text = path.read_text(encoding="utf-8")

    checks = [
        ("revision id", 'revision = "20260902_2015"' in text),
        ("correct parent", 'down_revision = "20260830_1006"' in text),
        ("source_type enum", "ALTER TYPE source_type" in text),
        ("OSINT label", "ADD VALUE IF NOT EXISTS 'OSINT'" in text),
        ("before OTHER", "BEFORE 'OTHER'" in text),
        ("autocommit block", "autocommit_block()" in text),
        ("no model/table rewrite", "ALTER TABLE" not in text),
    ]

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nMIGRATION: {path}")
    print(f"RESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
