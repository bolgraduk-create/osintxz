"""
Tests for comparison rules.
"""

from app.entity_resolution.rules import (
    ExactMatchRule,
)


def test_exact_match():

    rule = ExactMatchRule()


    assert rule.compare(
        "Test",
        "test",
    )


def test_not_match():

    rule = ExactMatchRule()


    assert not rule.compare(
        "John",
        "Alex",
    )