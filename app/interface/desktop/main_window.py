"""
Main desktop window.

Responsible for:

- application main window
- desktop layout foundation
- connecting navigation and pages

Does NOT:

- execute business logic
- access database
- call AI directly
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)


from app.interface.desktop.widgets.navigation_panel import (
    NavigationPanel,
)


from app.interface.desktop.widgets.header_bar import (
    HeaderBar,
)


from app.interface.desktop.widgets.status_bar import (
    StatusBar,
)


from app.interface.desktop.managers.page_manager import (
    PageManager,
)



class MainWindow(QMainWindow):
    """
    Main application window.
    """



    def __init__(
        self,
        container,
    ):

        super().__init__()


        self.container = container


        self.setWindowTitle(
            "OSINT Intelligence Platform"
        )


        self.setMinimumSize(
            1200,
            800,
        )


        self._setup_ui()



    # ==========================================================
    # UI Setup
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create main application layout.
        """


        root = QWidget()


        main_layout = QVBoxLayout(
            root
        )


        self.header = HeaderBar()


        self.status = StatusBar()


        content_layout = QHBoxLayout()


        self.navigation = NavigationPanel()


        self.pages = PageManager(
            self.container
        )


        content_layout.addWidget(
            self.navigation
        )


        content_layout.addWidget(
            self.pages
        )


        main_layout.addWidget(
            self.header
        )


        main_layout.addLayout(
            content_layout
        )


        main_layout.addWidget(
            self.status
        )


        self.setCentralWidget(
            root
        )


        self._connect_navigation()



    # ==========================================================
    # Navigation binding
    # ==========================================================

    def _connect_navigation(
        self,
    ) -> None:
        """
        Connect navigation buttons
        with page manager.
        """


        self.navigation.page_changed.connect(
            self.pages.show_page
        )