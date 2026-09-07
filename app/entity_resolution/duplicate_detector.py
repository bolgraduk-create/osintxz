"""
Duplicate entity detector.

Provides convenience methods for exact
canonical duplicate checks.

Responsibilities:

- use shared EntityNormalizer
- compare normalized identifier values
- provide backward-compatible helper methods

Does NOT:

- calculate fuzzy similarity
- calculate identity confidence
- decide complex entity identity
- merge entities
"""

from __future__ import annotations

from app.models.entity import (
    EntityType,
)

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)


class DuplicateDetector:
    """
    Detect exact duplicate entity values
    using the unified normalization contract.
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
    # Typed duplicate checks
    # ==========================================================

    def same_email(
        self,
        first: str,
        second: str,
    ) -> bool:

        return self._same(
            EntityType.EMAIL,
            first,
            second,
        )

    def same_phone(
        self,
        first: str,
        second: str,
    ) -> bool:

        return self._same(
            EntityType.PHONE,
            first,
            second,
        )

    def same_username(
        self,
        first: str,
        second: str,
    ) -> bool:

        return self._same(
            EntityType.USERNAME,
            first,
            second,
        )

    def same_domain(
        self,
        first: str,
        second: str,
    ) -> bool:

        return self._same(
            EntityType.DOMAIN,
            first,
            second,
        )

    def same_generic(
        self,
        first: str,
        second: str,
    ) -> bool:
        """
        Compare generic normalized text.

        This method is a utility only.

        Generic equality must NOT by itself be used
        as an automatic identity-resolution decision.
        """

        first_normalized = (
            self.normalizer
            .normalize_generic(
                first
            )
        )

        second_normalized = (
            self.normalizer
            .normalize_generic(
                second
            )
        )

        if (
            not first_normalized
            or not second_normalized
        ):

            return False

        return (
            first_normalized
            ==
            second_normalized
        )

    # ==========================================================
    # Generic typed helper
    # ==========================================================

    def same_by_type(
        self,
        entity_type: EntityType | str,
        first: str,
        second: str,
    ) -> bool:
        """
        Compare values using EntityType-aware
        canonical normalization.

        Unlike EntityComparator, this helper does
        not enforce automatic-resolution policy.

        It only answers whether canonical values
        are exactly equal.
        """

        resolved_type = (
            self._resolve_entity_type(
                entity_type
            )
        )

        if resolved_type is None:

            return False

        return self._same(
            resolved_type,
            first,
            second,
        )

    # ==========================================================
    # Internal comparison
    # ==========================================================

    def _same(
        self,
        entity_type: EntityType,
        first: str,
        second: str,
    ) -> bool:

        first_normalized = (
            self.normalizer.normalize(
                entity_type,
                first,
            )
        )

        second_normalized = (
            self.normalizer.normalize(
                entity_type,
                second,
            )
        )

        if (
            not first_normalized
            or not second_normalized
        ):

            return False

        return (
            first_normalized
            ==
            second_normalized
        )

    @staticmethod
    def _resolve_entity_type(
        entity_type: EntityType | str,
    ) -> EntityType | None:

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