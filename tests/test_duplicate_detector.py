"""
Tests for DuplicateDetector.
"""

from app.entity_resolution.duplicate_detector import (
    DuplicateDetector,
)


def test_same_email():

    detector = DuplicateDetector()

    assert detector.same_email(
        "John@Mail.com",
        "john@mail.com",
    )


def test_same_phone():

    detector = DuplicateDetector()

    assert detector.same_phone(
        "+38 (050) 111-22-33",
        "380501112233",
    )


def test_same_username():

    detector = DuplicateDetector()

    assert detector.same_username(
        "@John_Smith",
        "john_smith",
    )


def test_same_domain():

    detector = DuplicateDetector()

    assert detector.same_domain(
        "https://Example.com",
        "example.com/",
    )


def test_generic():

    detector = DuplicateDetector()

    assert detector.same_generic(
        "  John Smith ",
        "john smith",
    )