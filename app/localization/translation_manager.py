"""
Application translation manager.

Manages the active language and notifies subscribers when
the language changes.

This module does not depend on Qt, so it can be reused by
desktop, CLI, tests and future interfaces.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

from app.localization.language import (
    DEFAULT_LANGUAGE,
    LanguageCode,
    normalize_language_code,
)
from app.localization.registry import TranslationRegistry


LanguageChangedCallback = Callable[
    [LanguageCode],
    None,
]


class TranslationManager:
    """
    Central application localization service.
    """

    def __init__(
        self,
        *,
        registry: TranslationRegistry | None = None,
        default_language: LanguageCode | str = DEFAULT_LANGUAGE,
    ) -> None:
        self._registry = (
            registry
            if registry is not None
            else TranslationRegistry()
        )

        self._lock = RLock()

        self._subscribers: list[
            LanguageChangedCallback
        ] = []

        requested_language = normalize_language_code(
            default_language
        )

        if not self._registry.has_language(
            requested_language
        ):
            requested_language = DEFAULT_LANGUAGE

        self._current_language = (
            requested_language
        )

    @property
    def current_language(self) -> LanguageCode:
        """
        Return the currently active language.
        """

        with self._lock:
            return self._current_language

    @property
    def current_language_code(self) -> str:
        """
        Return the active language as a string code.
        """

        return self.current_language.value

    def available_languages(
        self,
    ) -> tuple[LanguageCode, ...]:
        """
        Return all registered languages.
        """

        return self._registry.languages()

    def set_language(
        self,
        language: LanguageCode | str,
    ) -> bool:
        """
        Change the active language.

        Returns:
            True when the language changed.
            False when it was already active.

        Raises:
            ValueError: If the language is unsupported.
        """

        normalized_language = (
            normalize_language_code(language)
        )

        if not self._registry.has_language(
            normalized_language
        ):
            raise ValueError(
                f"Unsupported language: {language!r}"
            )

        with self._lock:
            if (
                normalized_language
                == self._current_language
            ):
                return False

            self._current_language = (
                normalized_language
            )

            subscribers = tuple(
                self._subscribers
            )

        for callback in subscribers:
            callback(normalized_language)

        return True

    def translate(
        self,
        key: str,
        *,
        default: str | None = None,
        **values: Any,
    ) -> str:
        """
        Translate a key using the active language.

        Lookup order:

        1. Current language.
        2. Default English language.
        3. Explicit default value.
        4. Translation key itself.

        Values can be inserted with ``str.format``.
        """

        normalized_key = str(key).strip()

        if not normalized_key:
            return default or ""

        with self._lock:
            current_language = (
                self._current_language
            )

        translated_value = self._lookup(
            language=current_language,
            key=normalized_key,
        )

        if translated_value is None:
            translated_value = self._lookup(
                language=DEFAULT_LANGUAGE,
                key=normalized_key,
            )

        if translated_value is None:
            translated_value = (
                default
                if default is not None
                else normalized_key
            )

        if not values:
            return translated_value

        try:
            return translated_value.format(
                **values
            )
        except (KeyError, IndexError, ValueError):
            return translated_value

    def has_translation(
        self,
        key: str,
        language: LanguageCode | str | None = None,
    ) -> bool:
        """
        Check whether a translation exists.
        """

        normalized_key = str(key).strip()

        if not normalized_key:
            return False

        target_language = (
            self.current_language
            if language is None
            else normalize_language_code(
                language
            )
        )

        return (
            self._lookup(
                language=target_language,
                key=normalized_key,
            )
            is not None
        )

    def subscribe(
        self,
        callback: LanguageChangedCallback,
    ) -> None:
        """
        Subscribe to language changes.
        """

        if not callable(callback):
            raise TypeError(
                "Language change callback "
                "must be callable."
            )

        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(
                    callback
                )

    def unsubscribe(
        self,
        callback: LanguageChangedCallback,
    ) -> None:
        """
        Remove a language-change subscriber.
        """

        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(
                    callback
                )

    def _lookup(
        self,
        language: LanguageCode,
        key: str,
    ) -> str | None:
        translations = (
            self._registry.translations_for(
                language
            )
        )

        value = translations.get(key)

        if value is None:
            return None

        return str(value)