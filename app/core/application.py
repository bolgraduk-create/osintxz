"""
Application bootstrap.

Responsible for:

- creating QApplication
- initializing database
- creating session
- creating service container
- creating main window
- starting desktop application

This is the desktop entry point.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database.init_db import init_database
from app.database.session import create_session

from app.core.service_container import (
    ServiceContainer,
)

from app.interface.desktop.main_window import (
    MainWindow,
)


class Application:
    """
    Desktop application bootstrap.
    """

    def __init__(
        self,
    ) -> None:

        init_database()

        self.qt = QApplication(
            sys.argv
        )

        self.session = create_session()

        self.container = ServiceContainer(
            self.session
        )

        self.window = MainWindow(
            self.container
        )

    def run(
        self,
    ) -> int:
        """
        Start application.
        """

        self.window.show()

        code = self.qt.exec()

        self.session.close()

        return code