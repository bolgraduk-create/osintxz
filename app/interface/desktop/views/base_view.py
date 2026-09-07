"""
Base desktop view.

Responsible for:

- common view structure
- shared QWidget initialization
- optional reactive localization initialization
- localization lifecycle cleanup

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations

from PySide6.QtGui import (
    QCloseEvent,
)

from PySide6.QtWidgets import (
    QWidget,
)

from app.interface.desktop.localization.translatable import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
)


class BaseView(
    TranslatableMixin,
    QWidget,
):
    """
    Base class for desktop interface views.

    UI creation happens before translation initialization so that
    retranslate_ui() can safely access every created widget.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        QWidget.__init__(
            self,
            parent,
        )

        self._setup_ui()

        if translation_manager is not None:

            self.initialize_translations(
                translation_manager
            )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Set up the view interface.

        Child views override this method.
        """

        pass

    # ==========================================================
    # Localization lifecycle
    # ==========================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        Disconnect localization updates when the view is closed.
        """

        self.dispose_translations()

        super().closeEvent(
            event
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, str]:
        """
        Return view metadata.
        """

        return {
            "type": "desktop_view",
            "name": type(self).__name__,
        }