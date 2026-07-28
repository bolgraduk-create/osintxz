"""
Entity comparator.

Uses comparison rules
to detect duplicates.
"""

from __future__ import annotations


from app.models.entity import (
    EntityType,
)

from app.entity_resolution.rules import (
    COMPARISON_RULES,
)



class EntityComparator:
    """
    Compare entities using rules.
    """

    def compare(
        self,
        entity_type: EntityType,
        first: str,
        second: str,
    ) -> bool:
        """
        Compare two entity values.
        """

        rule = COMPARISON_RULES.get(
            entity_type
        )


        if rule is None:
            return False


        return rule.compare(
            first,
            second,
        )