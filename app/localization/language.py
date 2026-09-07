"""
Supported application languages.

This module contains language identifiers and metadata.
It does not depend on the desktop interface or Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LanguageCode(StrEnum):
    """
    Stable language identifiers used by the application.
    """

    ENGLISH = "en"
    RUSSIAN = "ru"
    UKRAINIAN = "uk"


@dataclass(frozen=True, slots=True)
class Language:
    """
    Describes one supported application language.
    """

    code: LanguageCode
    name: str
    native_name: str


SUPPORTED_LANGUAGES: tuple[Language, ...] = (
    Language(
        code=LanguageCode.ENGLISH,
        name="English",
        native_name="English",
    ),
    Language(
        code=LanguageCode.RUSSIAN,
        name="Russian",
        native_name="Русский",
    ),
    Language(
        code=LanguageCode.UKRAINIAN,
        name="Ukrainian",
        native_name="Українська",
    ),
)


DEFAULT_LANGUAGE = LanguageCode.ENGLISH


def normalize_language_code(
    value: LanguageCode | str | None,
) -> LanguageCode:
    """
    Convert a raw value into a supported LanguageCode.

    Unsupported or empty values fall back to DEFAULT_LANGUAGE.
    """

    if isinstance(value, LanguageCode):
        return value

    if value is None:
        return DEFAULT_LANGUAGE

    normalized_value = str(value).strip().lower()

    if not normalized_value:
        return DEFAULT_LANGUAGE

    aliases: dict[str, LanguageCode] = {
        "en": LanguageCode.ENGLISH,
        "eng": LanguageCode.ENGLISH,
        "english": LanguageCode.ENGLISH,
        "ru": LanguageCode.RUSSIAN,
        "rus": LanguageCode.RUSSIAN,
        "russian": LanguageCode.RUSSIAN,
        "русский": LanguageCode.RUSSIAN,
        "uk": LanguageCode.UKRAINIAN,
        "ua": LanguageCode.UKRAINIAN,
        "ukr": LanguageCode.UKRAINIAN,
        "ukrainian": LanguageCode.UKRAINIAN,
        "українська": LanguageCode.UKRAINIAN,
        "украинский": LanguageCode.UKRAINIAN,
    }

    return aliases.get(
        normalized_value,
        DEFAULT_LANGUAGE,
    )


def get_language(
    code: LanguageCode | str,
) -> Language:
    """
    Return metadata for a supported language.
    """

    normalized_code = normalize_language_code(code)

    for language in SUPPORTED_LANGUAGES:
        if language.code == normalized_code:
            return language

    raise ValueError(
        f"Unsupported language code: {code!r}"
    )