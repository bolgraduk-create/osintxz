"""
Desktop application bootstrap.

Responsible for:

- creating Qt application
- initializing application dependencies
- starting main window
- loading desktop theme

Does NOT:

- contain business logic
- access database directly
- perform analysis
"""

from __future__ import annotations


import sys


from PySide6.QtWidgets import (
    QApplication,
)


from app.interface.desktop.main_window import (
    MainWindow,
)


from app.interface.desktop.bootstrap.container import (
    DesktopContainer,
)


from app.interface.desktop.styles.theme import (
    APPLICATION_STYLE,
)



class DesktopApplication:
    """
    Main desktop application wrapper.
    """



    def __init__(
        self,
    ):

        self.qt_app = QApplication(
            sys.argv
        )


        self.qt_app.setStyleSheet(
            APPLICATION_STYLE
        )


        self.container = (
            DesktopContainer()
        )


        self.window = MainWindow(
            self.container
        )



    # ==========================================================
    # Execution
    # ==========================================================

    def run(
        self,
    ) -> int:
        """
        Start desktop application.
        """

        self.window.show()

        try:
            return self.qt_app.exec()
        finally:
            self.container.close()