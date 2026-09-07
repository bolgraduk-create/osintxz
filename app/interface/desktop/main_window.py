"""
Main desktop window.

Responsible for:

- application main window
- desktop layout foundation
- connecting navigation and pages
- providing the global application shell

Does NOT:

- execute business logic
- access database
- call AI directly
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.managers.page_manager import (
    PageManager,
)
from app.interface.desktop.widgets.header_bar import (
    HeaderBar,
)
from app.interface.desktop.widgets.navigation_panel import (
    NavigationPanel,
)
from app.interface.desktop.widgets.status_bar import (
    StatusBar,
)


class MainWindow(QMainWindow):
    """
    Main application window.

    Provides the permanent desktop shell:

    Header
        ↓
    Navigation + active page
        ↓
    Status bar
    """

    def __init__(
        self,
        container,
    ) -> None:

        super().__init__()

        self.container = container

        self.setObjectName(
            "MainWindow"
        )

        self.setWindowTitle(
            "OSINT Intelligence Platform"
        )

        self.setMinimumSize(
            1200,
            800,
        )

        self.resize(
            1440,
            900,
        )

        self._setup_ui()
        self._connect_navigation()
        self._show_initial_page()

    # ==========================================================
    # UI setup
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create the main application shell.
        """

        self.root = QWidget(
            self
        )

        self.root.setObjectName(
            "ApplicationRoot"
        )

        self.setCentralWidget(
            self.root
        )

        self.root_layout = QVBoxLayout(
            self.root
        )

        self.root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.root_layout.setSpacing(
            0
        )

        self._create_header()
        self._create_workspace()
        self._create_status_bar()

    def _create_header(
        self,
    ) -> None:
        """
        Create the permanent application header.
        """

        self.header = HeaderBar(
            translation_manager=(
                self.container.translation_manager
            )
        )

        self.header.setObjectName(
            "ApplicationHeader"
        )

        self.header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.root_layout.addWidget(
            self.header
        )

    def _create_workspace(
        self,
    ) -> None:
        """
        Create navigation and page workspace.
        """

        self.workspace = QFrame(
            self.root
        )

        self.workspace.setObjectName(
            "ApplicationWorkspace"
        )

        self.workspace_layout = QHBoxLayout(
            self.workspace
        )

        self.workspace_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.workspace_layout.setSpacing(
            0
        )

        self._create_navigation()
        self._create_content_area()

        self.root_layout.addWidget(
            self.workspace,
            1,
        )

    def _create_navigation(
        self,
    ) -> None:
        """
        Create the permanent navigation panel.
        """

        self.navigation_container = QFrame(
            self.workspace
        )

        self.navigation_container.setObjectName(
            "NavigationContainer"
        )

        self.navigation_container.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        navigation_layout = QVBoxLayout(
            self.navigation_container
        )

        navigation_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        navigation_layout.setSpacing(
            0
        )

        self.navigation = NavigationPanel(
            translation_manager=(
                self.container.translation_manager
            )
        )

        self.navigation.setObjectName(
            "MainNavigation"
        )

        navigation_layout.addWidget(
            self.navigation
        )

        self.workspace_layout.addWidget(
            self.navigation_container
        )

    def _create_content_area(
        self,
    ) -> None:
        """
        Create the active page area.
        """

        self.content_container = QFrame(
            self.workspace
        )

        self.content_container.setObjectName(
            "ContentContainer"
        )

        self.content_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        content_layout = QVBoxLayout(
            self.content_container
        )

        content_layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        content_layout.setSpacing(
            0
        )

        self.page_surface = QFrame(
            self.content_container
        )

        self.page_surface.setObjectName(
            "PageSurface"
        )

        page_surface_layout = QVBoxLayout(
            self.page_surface
        )

        page_surface_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        page_surface_layout.setSpacing(
            0
        )

        self.pages = PageManager(
            self.container
        )

        self.pages.setObjectName(
            "PageManager"
        )

        page_surface_layout.addWidget(
            self.pages
        )

        content_layout.addWidget(
            self.page_surface
        )

        self.workspace_layout.addWidget(
            self.content_container,
            1,
        )

    def _create_status_bar(
        self,
    ) -> None:
        """
        Create the permanent application status bar.
        """

        self.status = StatusBar()

        self.status.setObjectName(
            "ApplicationStatusBar"
        )

        self.status.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.root_layout.addWidget(
            self.status
        )

    # ==========================================================
    # Navigation binding
    # ==========================================================

    def _connect_navigation(
        self,
    ) -> None:
        """
        Connect navigation buttons with the page manager
        and application header.
        """

        self.navigation.page_changed.connect(
            self._handle_page_change
        )

    def _show_initial_page(
        self,
    ) -> None:
        """
        Display the initial application page and header context.
        """

        self._handle_page_change(
            "cases"
        )

    def _handle_page_change(
        self,
        page_name: str,
    ) -> None:
        """
        Handle global application page changes.
        """

        page_context_keys = {
            "cases": (
                "navigation.cases",
                "header.cases_subtitle",
            ),
            "osint": (
                "navigation.osint",
                "header.osint_subtitle",
            ),
            "evidence": (
                "navigation.evidence",
                "header.evidence_subtitle",
            ),
            "entities": (
                "navigation.entities",
                "header.entities_subtitle",
            ),
            "reports": (
                "navigation.reports",
                "header.reports_subtitle",
            ),
            "ai": (
                "navigation.ai",
                "header.ai_subtitle",
            ),
        }

        self.pages.show_page(
            page_name
        )

        title_key, subtitle_key = (
            page_context_keys.get(
                page_name,
                (
                    "app.name",
                    None,
                ),
            )
        )

        self.header.set_page_context_keys(
            title_key=title_key,
            subtitle_key=subtitle_key,
        )