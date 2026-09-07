"""
Desktop page manager.

Responsible for:

- storing application pages
- switching active pages
- opening selected investigation workspaces
- refreshing pages when they become active

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QStackedWidget,
)

from app.interface.desktop.pages.ai_page import (
    AIPage,
)
from app.interface.desktop.pages.case_workspace_page import (
    CaseWorkspacePage,
)
from app.interface.desktop.pages.cases_page import (
    CasesPage,
)
from app.interface.desktop.pages.entities_page import (
    EntitiesPage,
)
from app.interface.desktop.pages.evidence_page import (
    EvidencePage,
)
from app.interface.desktop.pages.osint_workspace_page import (
    OsintWorkspacePage,
)
from app.interface.desktop.pages.reports_page import (
    ReportsPage,
)


class PageManager(QStackedWidget):
    """
    Controls desktop application pages.
    """

    def __init__(
        self,
        container,
    ) -> None:

        super().__init__()

        self.container = container

        self.pages: dict[
            str,
            Any,
        ] = {}

        self._register_pages()
        self._setup_pages()

    # ==========================================================
    # Registration
    # ==========================================================

    def _register_pages(
        self,
    ) -> None:
        """
        Create page instances.
        """

        self.pages = {
            "cases": CasesPage(
                self.container,
                self.open_case,
            ),
            "case_workspace": CaseWorkspacePage(
                self.container
            ),
            "osint": OsintWorkspacePage(
                self.container
            ),
            "entities": EntitiesPage(
                self.container
            ),
            "evidence": EvidencePage(
                self.container
            ),
            "reports": ReportsPage(
                self.container
            ),
            "ai": AIPage(
                self.container
            ),
        }

    # ==========================================================
    # Setup
    # ==========================================================

    def _setup_pages(
        self,
    ) -> None:
        """
        Add pages to the stack.
        """

        for page in self.pages.values():

            self.addWidget(
                page
            )

    # ==========================================================
    # Navigation
    # ==========================================================

    def show_page(
        self,
        name: str,
    ) -> None:
        """
        Display the selected page.
        """

        page = self.pages.get(
            name
        )

        if page is None:

            return

        self.setCurrentWidget(
            page
        )

        refresh_method = getattr(
            page,
            "refresh",
            None,
        )

        if callable(
            refresh_method
        ):

            refresh_method()

    def current_page_name(
        self,
    ) -> str | None:
        """
        Return the registered name of the active page.
        """

        current_page = self.currentWidget()

        for page_name, page in self.pages.items():

            if page is current_page:

                return page_name

        return None

    # ==========================================================
    # Case workspace
    # ==========================================================

    def open_case(
        self,
        case: dict[str, Any],
    ) -> None:
        """
        Open the selected investigation workspace.

        The selected case is also propagated to pages that operate
        in the context of the current investigation.
        """

        if not isinstance(
            case,
            dict,
        ):

            return

        workspace_page = self.pages.get(
            "case_workspace"
        )

        if workspace_page is None:

            return

        workspace_load_case = getattr(
            workspace_page,
            "load_case",
            None,
        )

        if not callable(
            workspace_load_case
        ):

            return

        workspace_load_case(
            case
        )

        context_page_names = (
            "ai",
            "osint",
            "entities",
            "evidence",
            "reports",
        )

        for page_name in context_page_names:

            page = self.pages.get(
                page_name
            )

            if page is None:

                continue

            page_load_case = getattr(
                page,
                "load_case",
                None,
            )

            if callable(
                page_load_case
            ):

                page_load_case(
                    case
                )

        self.setCurrentWidget(
            workspace_page
        )