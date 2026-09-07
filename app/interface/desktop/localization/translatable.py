"""
Reactive localization support for desktop interface components.

The mixin connects a desktop component to TranslationManager
and invokes retranslate_ui() whenever the active language changes.

It does not depend on Qt directly, so it can be reused by pages,
views, widgets and windows without creating multiple-inheritance
problems with QWidget.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from weakref import ReferenceType
from weakref import ref

from app.localization import (
    LanguageCode,
    TranslationManager,
)


class TranslatableMixin:
    """
    Adds reactive localization support to an interface component.

    Classes using this mixin must implement:

        retranslate_ui()

    Initialization is explicit rather than constructor-based.
    This prevents conflicts with QWidget and other Qt classes.
    """

    def initialize_translations(
        self,
        translation_manager: TranslationManager,
        *,
        retranslate_immediately: bool = True,
    ) -> None:
        """
        Connect this component to a TranslationManager.

        This method should be called after all translated widgets
        have been created.

        Args:
            translation_manager:
                Shared application TranslationManager.

            retranslate_immediately:
                Whether retranslate_ui() should be called directly
                after the component is connected.
        """

        if not isinstance(
            translation_manager,
            TranslationManager,
        ):
            raise TypeError(
                "translation_manager must be "
                "a TranslationManager"
            )

        self.dispose_translations()

        self._translation_manager = (
            translation_manager
        )

        component_reference: ReferenceType[
            TranslatableMixin
        ] = ref(self)

        callback_holder: dict[
            str,
            Callable[[LanguageCode], None],
        ] = {}

        def language_changed_callback(
            language: LanguageCode,
        ) -> None:
            component = component_reference()

            if component is None:
                callback = callback_holder.get(
                    "callback"
                )

                if callback is not None:
                    translation_manager.unsubscribe(
                        callback
                    )

                return

            component._handle_language_changed(
                language
            )

        callback_holder["callback"] = (
            language_changed_callback
        )

        self._translation_callback = (
            language_changed_callback
        )

        translation_manager.subscribe(
            language_changed_callback
        )

        if retranslate_immediately:
            self.retranslate_ui()

    def dispose_translations(
        self,
    ) -> None:
        """
        Disconnect this component from language updates.

        This method is safe to call more than once.
        """

        translation_manager = getattr(
            self,
            "_translation_manager",
            None,
        )

        callback = getattr(
            self,
            "_translation_callback",
            None,
        )

        if (
            isinstance(
                translation_manager,
                TranslationManager,
            )
            and callback is not None
        ):
            translation_manager.unsubscribe(
                callback
            )

        self._translation_manager = None
        self._translation_callback = None

    @property
    def translation_manager(
        self,
    ) -> TranslationManager:
        """
        Return the TranslationManager connected to the component.

        Raises:
            RuntimeError:
                If localization has not been initialized.
        """

        translation_manager = getattr(
            self,
            "_translation_manager",
            None,
        )

        if not isinstance(
            translation_manager,
            TranslationManager,
        ):
            raise RuntimeError(
                "Translations have not been initialized "
                "for this component."
            )

        return translation_manager

    @property
    def translations_initialized(
        self,
    ) -> bool:
        """
        Return whether localization is initialized.
        """

        return isinstance(
            getattr(
                self,
                "_translation_manager",
                None,
            ),
            TranslationManager,
        )

    def translate(
        self,
        key: str,
        *,
        default: str | None = None,
        **values: Any,
    ) -> str:
        """
        Translate a key using the component TranslationManager.
        """

        return self.translation_manager.translate(
            key,
            default=default,
            **values,
        )

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply translated text to the component interface.

        Every translatable component must override this method.
        """

        raise NotImplementedError(
            f"{type(self).__name__} must implement "
            "retranslate_ui()."
        )

    def _handle_language_changed(
        self,
        language: LanguageCode,
    ) -> None:
        """
        Process a TranslationManager language-change event.
        """

        del language

        self.retranslate_ui()