"""
Built-in application translations.
"""

from app.localization.locales.en import (
    TRANSLATIONS as ENGLISH_TRANSLATIONS,
)
from app.localization.locales.ru import (
    TRANSLATIONS as RUSSIAN_TRANSLATIONS,
)
from app.localization.locales.uk import (
    TRANSLATIONS as UKRAINIAN_TRANSLATIONS,
)

__all__ = [
    "ENGLISH_TRANSLATIONS",
    "RUSSIAN_TRANSLATIONS",
    "UKRAINIAN_TRANSLATIONS",
]