from pathlib import Path

PERSISTENCE = Path("app/osint/finding_persistence.py")
SOURCE_MODEL = Path("app/models/source.py")


def test_osint_persistence_uses_original_path():
    text = PERSISTENCE.read_text(encoding="utf-8")

    assert 'and (source.original_path or "") == path' in text
    assert 'and (source.path or "") == path' not in text


def test_source_model_contract_has_original_path_not_path():
    text = SOURCE_MODEL.read_text(encoding="utf-8")

    assert "original_path: Mapped[str | None]" in text
    assert "\n    path: Mapped[" not in text
