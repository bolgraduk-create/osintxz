"""
Entity comparison rules.

Defines comparison behavior
for different entity types.
"""

from __future__ import annotations

from app.models.entity import EntityType


class ComparisonRule:
    """
    Base comparison rule.
    """

    def compare(
        self,
        first: str,
        second: str,
    ) -> bool:
        raise NotImplementedError



class ExactMatchRule(
    ComparisonRule,
):
    """
    Exact normalized match.
    """

    def compare(
        self,
        first: str,
        second: str,
    ) -> bool:

        return (
            first.strip().lower()
            ==
            second.strip().lower()
        )



COMPARISON_RULES = {

    EntityType.EMAIL:
        ExactMatchRule(),

    EntityType.USERNAME:
        ExactMatchRule(),

    EntityType.DOMAIN:
        ExactMatchRule(),

    EntityType.PHONE:
        ExactMatchRule(),

}