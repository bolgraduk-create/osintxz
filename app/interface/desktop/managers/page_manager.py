"""
Desktop page manager.

Responsible for:

- storing application pages
- switching active pages

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QStackedWidget,
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


from app.interface.desktop.pages.reports_page import (
    ReportsPage,
)


from app.interface.desktop.pages.ai_page import (
    AIPage,
)


from app.interface.desktop.pages.case_workspace_page import (
    CaseWorkspacePage,
)



class PageManager(QStackedWidget):
    """
    Controls desktop application pages.
    """



    def __init__(
        self,
        container,
    ):

        super().__init__()


        self.container = container


        self.pages = {}


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

            "cases":
                CasesPage(
                    self.container,
                    self.open_case,
                ),


            "case_workspace":
                CaseWorkspacePage(
                    self.container
                ),


            "entities":
                EntitiesPage(
                    self.container
                ),


            "evidence":
                EvidencePage(
                    self.container
                ),


            "reports":
                ReportsPage(
                    self.container
                ),


            "ai":
                AIPage(
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
        Add pages to stack.
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
        Display selected page.
        """


        page = self.pages.get(
            name
        )


        if page is None:

            return


        self.setCurrentWidget(
            page
        )



    # ==========================================================
    # Case workspace
    # ==========================================================

    def open_case(
        self,
        case: dict,
    ) -> None:
        """
        Open selected case workspace.
        """


        workspace = self.pages.get(
            "case_workspace"
        )


        if workspace is None:

            return


        workspace.load_case(
            case
        )


        self.setCurrentWidget(
            workspace
        )