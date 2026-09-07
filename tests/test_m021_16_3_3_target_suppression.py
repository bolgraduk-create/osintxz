from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery
from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.processing.extraction.contracts import ExtractionCandidate


def _candidate(value: str):
    return ExtractionCandidate(
        entity_type=EntityType.URL,
        value=value,
        normalized_value=value,
        confidence=0.9,
        metadata={},
    )


def test_query_target_url_is_suppressed_even_from_other_document():
    query = OpenWebQuery(
        target_type=OsintTargetType.URL,
        value="https://target.example/item/42",
    )
    document = OpenWebDocument(
        url="https://archive.example/capture",
        provider="common_crawl",
        text="",
    )

    candidates = [
        _candidate("https://target.example/item/42"),
        _candidate("https://new.example/profile"),
    ]

    accepted, skipped = OpenWebIdentifierExtractionBridge._filter_quality_candidates(
        candidates,
        document=document,
        query=query,
    )

    assert skipped == 1
    assert [item.value for item in accepted] == [
        "https://new.example/profile"
    ]
