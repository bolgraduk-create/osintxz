from __future__ import annotations

from pathlib import Path

from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)


def test_generic_persist_findings_entry_point_exists():
    assert hasattr(
        OsintFindingPersistenceService,
        "persist_findings",
    )


def test_generic_entry_point_reuses_existing_private_persistence_core():
    source = Path(
        "app/osint/finding_persistence.py"
    ).read_text(encoding="utf-8")

    start = source.index(
        "    def persist_findings("
    )
    end = source.index(
        "    def _persist_finding(",
        start,
    )
    block = source[start:end]

    assert "self._persist_finding(" in block
    assert "create_source(" not in block
    assert "create_evidence(" not in block
    assert "create_entity(" not in block
