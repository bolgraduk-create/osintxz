"""
Application localization package.
"""

from app.localization.language import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    Language,
    LanguageCode,
    get_language,
    normalize_language_code,
)
from app.localization.registry import (
    TranslationRegistry,
)
from app.localization.translation_manager import (
    LanguageChangedCallback,
    TranslationManager,
)
from app.localization.translator import (
    configure_translator,
    get_translation_manager,
    is_translator_configured,
    tr,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "Language",
    "LanguageCode",
    "LanguageChangedCallback",
    "TranslationManager",
    "TranslationRegistry",
    "configure_translator",
    "get_language",
    "get_translation_manager",
    "is_translator_configured",
    "normalize_language_code",
    "tr",
]