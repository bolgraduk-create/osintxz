"""
Desktop application.

Responsible for:

- creating QApplication
- applying the global desktop theme
- creating MainWindow
- starting desktop UI

Does NOT:

- execute business logic
- access repositories
- perform investigation processing
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
)

from app.interface.desktop.main_window import (
    MainWindow,
)
from app.interface.desktop.theme import (
    ThemeManager,
)


class DesktopApplication:
    """
    Desktop application bootstrap.
    """

    def __init__(
        self,
        container,
    ) -> None:

        self.container = container

        self.app = QApplication(
            sys.argv,
        )

        self.app.setApplicationName(
            "OSINT Intelligence Platform"
        )

        self.app.setOrganizationName(
            "OSINT Intelligence"
        )

        self.app.setStyle(
            "Fusion"
        )

        self.theme_manager = ThemeManager(
            self.app
        )

        self.theme_manager.apply_theme()

        self.window = MainWindow(
            container=self.container,
        )

    # ==========================================================
    # Run
    # ==========================================================

    def run(
        self,
    ) -> int:
        """
        Start desktop application.
        """

        self.window.show()

        return self.app.exec()