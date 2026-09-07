"""
Convenient application-wide translation helper.

The active TranslationManager must be configured by the
application composition root before translations are used.
"""

from __future__ import annotations

from typing import Any

from app.localization.translation_manager import (
    TranslationManager,
)


_translation_manager: TranslationManager | None = None


def configure_translator(
    manager: TranslationManager,
) -> None:
    """
    Configure the application-wide TranslationManager.

    The ServiceContainer should call this once during
    application startup.
    """

    if not isinstance(
        manager,
        TranslationManager,
    ):
        raise TypeError(
            "manager must be a TranslationManager"
        )

    global _translation_manager
    _translation_manager = manager


def is_translator_configured() -> bool:
    """
    Return whether the global translator is configured.
    """

    return _translation_manager is not None


def get_translation_manager() -> TranslationManager:
    """
    Return the configured TranslationManager.

    Raises:
        RuntimeError: If application localization has not
        been configured yet.
    """

    if _translation_manager is None:
        raise RuntimeError(
            "TranslationManager has not been configured."
        )

    return _translation_manager


def tr(
    key: str,
    *,
    default: str | None = None,
    **values: Any,
) -> str:
    """
    Translate a key through the configured manager.

    Raises:
        RuntimeError: If application localization has not
        been configured yet.
    """

    manager = get_translation_manager()

    return manager.translate(
        key,
        default=default,
        **values,
    )