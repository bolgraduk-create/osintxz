"""
Duplicate entity detector.

Compares normalized entities.
"""

from __future__ import annotations

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)


class DuplicateDetector:
    """
    Detect duplicate entities.
    """

    def __init__(self) -> None:
        self.normalizer = EntityNormalizer()

    def same_email(
        self,
        first: str,
        second: str,
    ) -> bool:
        return (
            self.normalizer.normalize_email(first)
            ==
            self.normalizer.normalize_email(second)
        )

    def same_phone(
        self,
        first: str,
        second: str,
    ) -> bool:
        return (
            self.normalizer.normalize_phone(first)
            ==
            self.normalizer.normalize_phone(second)
        )

    def same_username(
        self,
        first: str,
        second: str,
    ) -> bool:
        return (
            self.normalizer.normalize_username(first)
            ==
            self.normalizer.normalize_username(second)
        )

    def same_domain(
        self,
        first: str,
        second: str,
    ) -> bool:
        return (
            self.normalizer.normalize_domain(first)
            ==
            self.normalizer.normalize_domain(second)
        )

    def same_generic(
        self,
        first: str,
        second: str,
    ) -> bool:
        return (
            self.normalizer.normalize_generic(first)
            ==
            self.normalizer.normalize_generic(second)
        )