from pathlib import Path
from types import SimpleNamespace

from app.application.investigation_result_consolidation import consolidate_result_rows
from app.application.person_name_relevance import (
    match_person_name_record,
    match_person_name_texts,
)


def test_full_two_part_name_is_required_not_one_token():
    assert match_person_name_texts("Марк Кириченко", ["Марк Кириченко"]).accepted
    assert not match_person_name_texts("Марк Кириченко", ["Иван Кириченко"]).accepted
    assert not match_person_name_texts("Марк Кириченко", ["Марк Твен"]).accepted


def test_name_order_does_not_matter():
    result = match_person_name_texts("Марк Кириченко", ["Кириченко Марк"])
    assert result.accepted
    assert result.score == 100.0


def test_cyrillic_to_common_latin_transliteration_matches():
    assert match_person_name_texts("Марк Кириченко", ["Mark Kirichenko"]).accepted
    assert match_person_name_texts("Марк Кириченко", ["Mark Kyrychenko"]).accepted


def test_three_part_name_requires_first_and_last_but_middle_can_be_missing():
    result = match_person_name_texts(
        "Марк Александрович Кириченко",
        ["Mark Kirichenko"],
    )
    assert result.accepted
    assert result.reason == "first_last_match"
    assert not match_person_name_texts(
        "Марк Александрович Кириченко",
        ["Александр Кириченко"],
    ).accepted


def test_structured_author_metadata_can_validate_publication_result():
    record = SimpleNamespace(
        display_name="A paper about network analysis",
        attributes={
            "authors": [
                {"name": "Mark Kyrychenko"},
                {"name": "Other Author"},
            ]
        },
        metadata={},
    )
    result = match_person_name_record("Марк Кириченко", record)
    assert result.accepted
    assert result.matched_text == "Mark Kyrychenko"


def test_clean_view_suppresses_same_surname_and_mark_twain_but_raw_is_unchanged_upstream():
    rows = [
        {
            "lane": "Federation", "source": "a", "title": "Иван Кириченко",
            "detail": "Person", "type": "person", "seed": "Марк Кириченко",
            "seedType": "person_name", "candidateOnly": True,
        },
        {
            "lane": "Federation", "source": "b", "title": "Mark Twain",
            "detail": "Author", "type": "person", "seed": "Марк Кириченко",
            "seedType": "person_name", "candidateOnly": True,
        },
        {
            "lane": "Federation", "source": "c", "title": "Mark Kirichenko",
            "detail": "Academic author", "type": "person", "seed": "Марк Кириченко",
            "seedType": "person_name", "candidateOnly": True,
        },
    ]
    result = consolidate_result_rows(rows, seeds=[{"kind": "person_name", "value": "Марк Кириченко"}])
    assert result.rows == []
    assert [row["title"] for row in result.candidate_rows] == ["Mark Kirichenko"]
    assert result.low_value_suppressed == 2
    assert result.raw_count == 3


def test_preclassified_rejected_name_is_always_hidden_from_clean_view():
    rows = [{
        "lane": "Registry", "source": "x", "title": "Иван Кириченко",
        "type": "person", "seed": "Марк Кириченко", "seedType": "person_name",
        "identityRejected": True, "identityMatchScore": 50.0,
    }]
    result = consolidate_result_rows(rows)
    assert result.rows == []
    assert result.low_value_suppressed == 1


def test_person_name_automatic_routes_no_longer_use_generic_archive_or_keyword():
    source = Path("app/application/unified_investigation_search.py").read_text(encoding="utf-8")
    automatic = source.split("\n_CAPABILITY_PRIORITIES: dict", 1)[1]
    block = automatic.split("UnifiedSeedKind.PERSON_NAME: (", 1)[1].split("),", 1)[0]
    assert '"name"' in block
    assert '"person"' in block
    assert '"author"' in block
    assert '"academic_author"' in block
    assert '"archive_search"' not in block
    assert '"keyword"' not in block


def test_worker_filters_name_records_before_pivot_extraction_but_keeps_raw_rows():
    source = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    assert "match_person_name_record(seed.value, record)" in source
    assert "records.extend(accepted_records)" in source
    assert '"identityRejected": identity_rejected' in source
    assert "Raw UI output is still built from every upstream row" in source
