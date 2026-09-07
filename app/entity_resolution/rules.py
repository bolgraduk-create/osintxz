"""
Entity comparison rules.

Defines low-level comparison behavior
for already normalized entity values.

Responsibilities:

- define comparison rule contracts
- compare canonical entity values
- keep automatic exact-match policy explicit

Does NOT:

- normalize values
- calculate fuzzy similarity
- calculate identity confidence
- merge entities
"""

from __future__ import annotations

from app.models.entity import (
    EntityType,
)


class ComparisonRule:
    """
    Base entity comparison rule.
    """

    def compare(
        self,
        first: str,
        second: str,
    ) -> bool:
        """
        Compare two already normalized values.
        """

        raise NotImplementedError


class ExactMatchRule(
    ComparisonRule,
):
    """
    Exact canonical-value comparison.

    Empty canonical values never match.
    """

    def compare(
        self,
        first: str,
        second: str,
    ) -> bool:

        if not first or not second:

            return False

        return (
            first
            ==
            second
        )


# ==========================================================
# Automatic exact-resolution policy
# ==========================================================
#
# IMPORTANT:
#
# Only identifiers for which exact canonical equality
# is currently considered strong enough for automatic
# duplicate resolution belong here.
#
# PERSON / ORGANIZATION / LOCATION etc. are intentionally
# excluded. They will later use multi-signal resolution.
# ==========================================================

COMPARISON_RULES: dict[
    EntityType,
    ComparisonRule,
] = {

    EntityType.EMAIL:
        ExactMatchRule(),

    EntityType.USERNAME:
        ExactMatchRule(),

    EntityType.DOMAIN:
        ExactMatchRule(),

    EntityType.PHONE:
        ExactMatchRule(),

    EntityType.BANK_CARD:
        ExactMatchRule(),
}