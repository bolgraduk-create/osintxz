"""Block 10.4 regression tests for conservative phone extraction."""

from __future__ import annotations

import pytest

from app.analysis.analyzers.entity_analyzer import EntityAnalyzer
from app.models.entity import EntityType
from app.processing.extraction import IdentifierExtractor


@pytest.fixture()
def analyzer() -> EntityAnalyzer:
    return EntityAnalyzer()


def _phone_entities(analyzer: EntityAnalyzer, text: str) -> list[dict]:
    return [
        entity
        for entity in analyzer.analyze(text)
        if entity["type"] == EntityType.PHONE.value
    ]


@pytest.mark.parametrize(
    ("raw", "expected_normalized"),
    [
        ("+380 67 123 45 67", "380671234567"),
        ("+380671234567", "380671234567"),
        ("380671234567", "380671234567"),
        ("0671234567", "0671234567"),
        ("067 123 45 67", "0671234567"),
        ("(067) 123-45-67", "0671234567"),
        ("+1 (202) 555-0147", "12025550147"),
        ("202-555-0147", "2025550147"),
    ],
)
def test_supported_phone_formats(
    analyzer: EntityAnalyzer,
    raw: str,
    expected_normalized: str,
) -> None:
    phones = _phone_entities(analyzer, f"Contact: {raw}")

    assert len(phones) == 1
    assert phones[0]["normalized"] == expected_normalized
    assert phones[0]["metadata"]["identifier_kind"] == "phone"


@pytest.mark.parametrize(
    "text",
    [
        "Date: 12.08.2026",
        "Date: 12-08-2026",
        "ISO date: 2026-08-12",
        "Time: 23:59",
        "Server: 127.0.0.1",
        "Reference ID: 1234567890123",
        "Reference ID: 12345678901234",
        "Reference ID: 123456789012345",
        "Noise: 1111111111",
        "Noise: 0000000000",
    ],
)
def test_common_false_positives_are_not_phones(
    analyzer: EntityAnalyzer,
    text: str,
) -> None:
    assert _phone_entities(analyzer, text) == []


def test_valid_bank_card_is_not_duplicated_as_phone(
    analyzer: EntityAnalyzer,
) -> None:
    entities = analyzer.analyze(
        "Payment test identifier: 4111 1111 1111 1111"
    )

    phone_entities = [
        entity
        for entity in entities
        if entity["type"] == EntityType.PHONE.value
    ]
    card_entities = [
        entity
        for entity in entities
        if entity["type"] == EntityType.BANK_CARD.value
    ]

    assert phone_entities == []
    assert len(card_entities) == 1
    assert card_entities[0]["normalized"] == "4111111111111111"


def test_phone_inside_url_is_not_extracted(
    analyzer: EntityAnalyzer,
) -> None:
    assert _phone_entities(
        analyzer,
        "https://example.org/profile/380671234567",
    ) == []


def test_mixed_message_extracts_only_real_phone_candidate(
    analyzer: EntityAnalyzer,
) -> None:
    text = (
        "Meeting 12.08.2026 at 23:59. "
        "Server 127.0.0.1. "
        "Reference 12345678901234. "
        "Call me: +380 (67) 123-45-67."
    )

    phones = _phone_entities(analyzer, text)

    assert len(phones) == 1
    assert phones[0]["normalized"] == "380671234567"


def test_identifier_extractor_preserves_phone_contract() -> None:
    extractor = IdentifierExtractor()

    candidates = extractor.extract(
        "Telegram message: +380 67 123 45 67"
    )

    phones = [
        candidate
        for candidate in candidates
        if candidate.entity_type == EntityType.PHONE
    ]

    assert len(phones) == 1
    assert phones[0].normalized_value == "380671234567"
    assert phones[0].metadata["identifier_kind"] == "phone"
