from pathlib import Path


def test_ui_groups_by_type_and_value():
    text = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")

    block = text.split("def _fill_entities", 1)[1].split(
        "def _fill_sources", 1
    )[0]

    assert "M021.16.3.3 unique entity presentation" in block
    assert '"evidence_ids": set()' in block
    assert "str(type_value).casefold()" in block
    assert "str(value).casefold()" in block
    assert 'f"{len(evidence_ids)} evidence"' in block
