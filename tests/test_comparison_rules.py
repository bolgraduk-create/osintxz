"""
Tests for canonical comparison rules.
"""

from app.entity_resolution.rules import ExactMatchRule


def test_exact_match():
    """ExactMatchRule compares values that are already canonicalized."""

    rule = ExactMatchRule()

    assert rule.compare(
        "test",
        "test",
    )


def test_not_match():
    rule = ExactMatchRule()

    assert not rule.compare(
        "john",
        "alex",
    )
