"""Block 10.5 regression tests for conservative card-like identifier extraction.

All numeric fixtures are synthetic test values used only to exercise Luhn
classification.  The tests do not perform issuer lookup or any account action.
"""

from __future__ import annotations

import pytest

from app.analysis.analyzers.entity_analyzer import EntityAnalyzer
from app.models.entity import EntityType
from app.processing.extraction import IdentifierExtractor


@pytest.fixture()
def analyzer() -> EntityAnalyzer:
    return EntityAnalyzer()


def _entities_of_type(
    analyzer: EntityAnalyzer,
    text: str,
    entity_type: EntityType,
) -> list[dict]:
    return [
        entity
        for entity in analyzer.analyze(text)
        if entity["type"] == entity_type.value
    ]


SYNTHETIC_16 = "1234567890123452"
SYNTHETIC_19 = "1234567890123456785"
SYNTHETIC_15_PHONE_COLLISION = "380671234567897"


@pytest.mark.parametrize(
    ("raw", "expected_formatting"),
    [
        (SYNTHETIC_16, "compact"),
        ("1234 5678 9012 3452", "spaced"),
        ("1234-5678-9012-3452", "hyphenated"),
        (SYNTHETIC_19, "compact"),
    ],
)
def test_luhn_valid_16_to_19_digit_candidates_are_detected(
    analyzer: EntityAnalyzer,
    raw: str,
    expected_formatting: str,
) -> None:
    cards = _entities_of_type(
        analyzer,
        f"Imported evidence value: {raw}",
        EntityType.BANK_CARD,
    )

    assert len(cards) == 1
    assert cards[0]["normalized"].isdigit()
    assert 16 <= len(cards[0]["normalized"]) <= 19
    assert cards[0]["metadata"]["validation"] == "luhn"
    assert cards[0]["metadata"]["formatting"] == expected_formatting
    assert cards[0]["metadata"]["classification"] == "outside_phone_range"


def test_invalid_luhn_candidate_is_rejected(
    analyzer: EntityAnalyzer,
) -> None:
    cards = _entities_of_type(
        analyzer,
        "Imported value: 1234 5678 9012 3456",
        EntityType.BANK_CARD,
    )

    assert cards == []


@pytest.mark.parametrize(
    "raw",
    [
        "0000 0000 0000 0000",
        "1111 1111 1111 1111",
    ],
)
def test_repeated_digit_sequences_are_rejected(
    analyzer: EntityAnalyzer,
    raw: str,
) -> None:
    cards = _entities_of_type(
        analyzer,
        f"Noise: {raw}",
        EntityType.BANK_CARD,
    )

    assert cards == []


def test_short_luhn_valid_value_without_card_context_stays_phone(
    analyzer: EntityAnalyzer,
) -> None:
    text = f"Call me: +{SYNTHETIC_15_PHONE_COLLISION}"

    cards = _entities_of_type(
        analyzer,
        text,
        EntityType.BANK_CARD,
    )
    phones = _entities_of_type(
        analyzer,
        text,
        EntityType.PHONE,
    )

    assert cards == []
    assert len(phones) == 1
    assert phones[0]["normalized"] == SYNTHETIC_15_PHONE_COLLISION


@pytest.mark.parametrize(
    "label",
    [
        "Card number",
        "Payment card",
        "Номер карты",
        "Номер картки",
    ],
)
def test_short_luhn_valid_value_requires_payment_context(
    analyzer: EntityAnalyzer,
    label: str,
) -> None:
    text = f"{label}: {SYNTHETIC_15_PHONE_COLLISION}"

    cards = _entities_of_type(
        analyzer,
        text,
        EntityType.BANK_CARD,
    )
    phones = _entities_of_type(
        analyzer,
        text,
        EntityType.PHONE,
    )

    assert len(cards) == 1
    assert cards[0]["normalized"] == SYNTHETIC_15_PHONE_COLLISION
    assert cards[0]["metadata"]["payment_context"] is True
    assert cards[0]["metadata"]["classification"] == "context_disambiguated"
    assert phones == []


def test_card_candidate_inside_url_is_not_extracted(
    analyzer: EntityAnalyzer,
) -> None:
    cards = _entities_of_type(
        analyzer,
        f"https://example.org/payment/{SYNTHETIC_16}",
        EntityType.BANK_CARD,
    )

    assert cards == []


def test_card_candidate_embedded_in_word_is_not_extracted(
    analyzer: EntityAnalyzer,
) -> None:
    cards = _entities_of_type(
        analyzer,
        f"ORDER{SYNTHETIC_16}REFERENCE",
        EntityType.BANK_CARD,
    )

    assert cards == []


def test_mixed_message_separates_phone_and_card(
    analyzer: EntityAnalyzer,
) -> None:
    text = (
        "Contact: +380 67 123 45 67. "
        f"Payment card: {SYNTHETIC_16}. "
        "Date: 12.08.2026. "
        "Server: 127.0.0.1."
    )

    cards = _entities_of_type(
        analyzer,
        text,
        EntityType.BANK_CARD,
    )
    phones = _entities_of_type(
        analyzer,
        text,
        EntityType.PHONE,
    )

    assert len(cards) == 1
    assert cards[0]["normalized"] == SYNTHETIC_16
    assert len(phones) == 1
    assert phones[0]["normalized"] == "380671234567"


def test_identifier_extractor_preserves_bank_card_contract() -> None:
    extractor = IdentifierExtractor()

    candidates = extractor.extract(
        f"Imported evidence: {SYNTHETIC_16}"
    )

    cards = [
        candidate
        for candidate in candidates
        if candidate.entity_type == EntityType.BANK_CARD
    ]

    assert len(cards) == 1
    assert cards[0].normalized_value == SYNTHETIC_16
    assert cards[0].metadata["identifier_kind"] == "bank_card"
    assert cards[0].metadata["validation"] == "luhn"
