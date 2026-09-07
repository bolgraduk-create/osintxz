from pathlib import Path


def _find_migration():
    for base in (Path("alembic/versions"), Path("migrations/versions")):
        if base.is_dir():
            for path in base.glob("*.py"):
                text = path.read_text(encoding="utf-8", errors="replace")
                if 'revision = "20260902_2015"' in text:
                    return path, text
    raise AssertionError("Migration 20260902_2015 not found")


def test_migration_chain_and_enum_label():
    path, text = _find_migration()
    assert 'down_revision = "20260830_1006"' in text
    assert "ALTER TYPE source_type" in text
    assert "ADD VALUE IF NOT EXISTS 'OSINT'" in text
    assert "autocommit_block()" in text


def test_migration_does_not_rewrite_sources_table():
    _, text = _find_migration()
    assert "ALTER TABLE sources" not in text
