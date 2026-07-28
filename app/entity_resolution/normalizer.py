"""
Entity normalization.

Provides canonical representation
for extracted entities.
"""

from __future__ import annotations

import re


class EntityNormalizer:
    """
    Normalizes entity values.
    """

    def normalize_email(
        self,
        value: str,
    ) -> str:
        return value.strip().lower()


    def normalize_username(
        self,
        value: str,
    ) -> str:
        value = value.strip().lower()

        if value.startswith("@"):
            value = value[1:]

        return value


    def normalize_phone(
        self,
        value: str,
    ) -> str:
        return re.sub(
            r"\D",
            "",
            value,
        )


    def normalize_domain(
        self,
        value: str,
    ) -> str:
        value = value.strip().lower()

        value = value.replace(
            "https://",
            "",
        )

        value = value.replace(
            "http://",
            "",
        )

        return value.rstrip("/")


    def normalize_generic(
        self,
        value: str,
    ) -> str:
        return value.strip().lower()