"""
Desktop application theme manager.

Responsible for:

- applying the application stylesheet
- configuring the application palette
- refreshing widget styles when properties change

Does NOT:

- create application windows
- manage interface navigation
- store user language settings
"""

from __future__ import annotations

from PySide6.QtGui import (
    QColor,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.stylesheet import (
    build_application_stylesheet,
)


class ThemeManager:
    """
    Applies and refreshes the desktop application theme.
    """

    def __init__(
        self,
        application: QApplication,
    ) -> None:

        self._application = application

    # ==========================================================
    # Theme
    # ==========================================================

    def apply_theme(
        self,
    ) -> None:
        """
        Apply the global application theme.
        """

        self._application.setPalette(
            self._build_palette()
        )

        self._application.setStyleSheet(
            build_application_stylesheet()
        )

    def refresh_theme(
        self,
    ) -> None:
        """
        Reapply the current application theme.
        """

        self.apply_theme()

        for widget in self._application.allWidgets():

            widget.style().unpolish(
                widget
            )

            widget.style().polish(
                widget
            )

            widget.update()

    # ==========================================================
    # Widget roles
    # ==========================================================

    @staticmethod
    def set_role(
        widget: QWidget,
        role: str,
    ) -> None:
        """
        Assign a reusable visual role to a widget.

        Example:

            ThemeManager.set_role(
                button,
                "primary",
            )
        """

        widget.setProperty(
            "role",
            role,
        )

        style = widget.style()

        style.unpolish(
            widget
        )

        style.polish(
            widget
        )

        widget.update()

    @staticmethod
    def clear_role(
        widget: QWidget,
    ) -> None:
        """
        Remove the visual role from a widget.
        """

        widget.setProperty(
            "role",
            None,
        )

        style = widget.style()

        style.unpolish(
            widget
        )

        style.polish(
            widget
        )

        widget.update()

    # ==========================================================
    # Palette
    # ==========================================================

    @staticmethod
    def _build_palette(
    ) -> QPalette:
        """
        Build the Qt palette matching the global stylesheet.
        """

        palette = QPalette()

        palette.setColor(
            QPalette.ColorRole.Window,
            QColor(
                AppColors.BACKGROUND
            ),
        )

        palette.setColor(
            QPalette.ColorRole.WindowText,
            QColor(
                AppColors.TEXT_PRIMARY
            ),
        )

        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(
                AppColors.INPUT_BACKGROUND
            ),
        )

        palette.setColor(
            QPalette.ColorRole.AlternateBase,
            QColor(
                AppColors.PANEL_SECONDARY
            ),
        )

        palette.setColor(
            QPalette.ColorRole.ToolTipBase,
            QColor(
                AppColors.PANEL
            ),
        )

        palette.setColor(
            QPalette.ColorRole.ToolTipText,
            QColor(
                AppColors.TEXT_PRIMARY
            ),
        )

        palette.setColor(
            QPalette.ColorRole.Text,
            QColor(
                AppColors.TEXT_PRIMARY
            ),
        )

        palette.setColor(
            QPalette.ColorRole.Button,
            QColor(
                AppColors.SURFACE
            ),
        )

        palette.setColor(
            QPalette.ColorRole.ButtonText,
            QColor(
                AppColors.TEXT_SECONDARY
            ),
        )

        palette.setColor(
            QPalette.ColorRole.BrightText,
            QColor(
                AppColors.TEXT_ON_ACCENT
            ),
        )

        palette.setColor(
            QPalette.ColorRole.Highlight,
            QColor(
                AppColors.SELECTION
            ),
        )

        palette.setColor(
            QPalette.ColorRole.HighlightedText,
            QColor(
                AppColors.TEXT_ON_ACCENT
            ),
        )

        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor(
                AppColors.TEXT_DISABLED
            ),
        )

        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(
                AppColors.TEXT_DISABLED
            ),
        )

        return palette