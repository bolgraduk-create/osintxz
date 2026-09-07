from app.models.entity import EntityType
from app.osint.open_web.contracts import OpenWebDocument
from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.processing.extraction.contracts import ExtractionCandidate


def _candidate(entity_type, value, normalized=None):
    return ExtractionCandidate(
        entity_type=entity_type,
        value=value,
        normalized_value=normalized or value,
        confidence=0.9,
        metadata={},
    )


def test_extraction_text_does_not_inject_document_url():
    document = OpenWebDocument(
        url="https://example.com/contact",
        provider="live_web",
        text="Call us at +1 312-996-7000",
    )
    text = OpenWebIdentifierExtractionBridge._build_extraction_text(document)
    assert "https://example.com/contact" not in text
    assert "+1 312-996-7000" in text


def test_self_url_filtered_other_url_kept():
    document = OpenWebDocument(
        url="https://example.com/contact/",
        provider="live_web",
        text="",
    )
    candidates = [
        _candidate(EntityType.URL, "https://example.com/contact"),
        _candidate(EntityType.URL, "https://other.example.org/team"),
    ]
    accepted, skipped = OpenWebIdentifierExtractionBridge._filter_quality_candidates(
        candidates,
        document=document,
    )
    assert skipped == 1
    assert len(accepted) == 1
    assert accepted[0].value == "https://other.example.org/team"


def test_numeric_ids_rejected_as_web_phones():
    for value in ("22336", "20993842", "1510000000", "20260903", "20260903142131"):
        assert OpenWebIdentifierExtractionBridge._plausible_open_web_phone(value) is False


def test_formatted_phone_numbers_kept():
    for value in ("+380 48 646 13 07", "+1 312-996-7000", "(04846) 4-13-07"):
        assert OpenWebIdentifierExtractionBridge._plausible_open_web_phone(value) is True
