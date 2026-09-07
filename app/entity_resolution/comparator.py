"""
Entity comparator.

Compares entity values using the shared
EntityNormalizer and comparison rules.

Responsibilities:

- resolve entity comparison rule
- canonicalize both values
- perform safe exact comparison
- preserve automatic-resolution policy

Does NOT:

- calculate fuzzy similarity
- calculate identity confidence
- merge entities
- access the database
"""

from __future__ import annotations

from app.models.entity import (
    EntityType,
)

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.entity_resolution.rules import (
    COMPARISON_RULES,
)


class EntityComparator:
    """
    Compare entity values using the unified
    normalization contract.
    """

    def __init__(
        self,
        normalizer: EntityNormalizer | None = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def compare(
        self,
        entity_type: EntityType | str,
        first: str,
        second: str,
    ) -> bool:
        """
        Compare two values of one entity type.

        Values are normalized before a comparison
        rule is applied.

        Unsupported entity types deliberately return
        False because exact equality alone is not
        considered sufficient for automatic resolution.
        """

        resolved_type = (
            self._resolve_entity_type(
                entity_type
            )
        )

        if resolved_type is None:

            return False

        rule = COMPARISON_RULES.get(
            resolved_type
        )

        if rule is None:

            return False

        first_normalized = (
            self.normalizer.normalize(
                resolved_type,
                first,
            )
        )

        second_normalized = (
            self.normalizer.normalize(
                resolved_type,
                second,
            )
        )

        return rule.compare(
            first_normalized,
            second_normalized,
        )

    def canonical_values(
        self,
        entity_type: EntityType | str,
        first: str,
        second: str,
    ) -> tuple[str, str] | None:
        """
        Return canonical values used for comparison.

        Useful for diagnostics and explainability.

        Returns None for an invalid entity type.
        """

        resolved_type = (
            self._resolve_entity_type(
                entity_type
            )
        )

        if resolved_type is None:

            return None

        return (
            self.normalizer.normalize(
                resolved_type,
                first,
            ),
            self.normalizer.normalize(
                resolved_type,
                second,
            ),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _resolve_entity_type(
        entity_type: EntityType | str,
    ) -> EntityType | None:
        """
        Resolve EntityType from enum or string.
        """

        if isinstance(
            entity_type,
            EntityType,
        ):

            return entity_type

        try:

            return EntityType(
                str(
                    entity_type
                )
                .strip()
                .lower()
            )

        except (
            TypeError,
            ValueError,
        ):

            return None