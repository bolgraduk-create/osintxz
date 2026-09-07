"""
Translation registry.

Stores dictionaries for all supported application languages.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.localization.language import LanguageCode
from app.localization.locales import (
    ENGLISH_TRANSLATIONS,
    RUSSIAN_TRANSLATIONS,
    UKRAINIAN_TRANSLATIONS,
)


TranslationDictionary = Mapping[str, str]


class TranslationRegistry:
    """
    Provides translation dictionaries by language.
    """

    def __init__(self) -> None:
        self._translations: dict[
            LanguageCode,
            dict[str, str],
        ] = {
            LanguageCode.ENGLISH: dict(
                ENGLISH_TRANSLATIONS
            ),
            LanguageCode.RUSSIAN: dict(
                RUSSIAN_TRANSLATIONS
            ),
            LanguageCode.UKRAINIAN: dict(
                UKRAINIAN_TRANSLATIONS
            ),
        }

    def languages(self) -> tuple[LanguageCode, ...]:
        """
        Return registered language codes.
        """

        return tuple(
            self._translations.keys()
        )

    def has_language(
        self,
        language: LanguageCode,
    ) -> bool:
        """
        Check whether a language is registered.
        """

        return language in self._translations

    def translations_for(
        self,
        language: LanguageCode,
    ) -> TranslationDictionary:
        """
        Return translations for a language.

        Raises:
            ValueError: If the language is not registered.
        """

        translations = self._translations.get(
            language
        )

        if translations is None:
            raise ValueError(
                f"Language is not registered: "
                f"{language.value}"
            )

        return translations

    def register(
        self,
        language: LanguageCode,
        translations: Mapping[str, str],
        *,
        replace: bool = False,
    ) -> None:
        """
        Register translations for a language.
        """

        if (
            language in self._translations
            and not replace
        ):
            raise ValueError(
                f"Language is already registered: "
                f"{language.value}"
            )

        self._translations[language] = dict(
            translations
        )