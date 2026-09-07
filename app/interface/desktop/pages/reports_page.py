"""
Reports page.

Responsible for:

- displaying reports workspace
- embedding report view

Does NOT:

- execute business logic
- access database
- call services directly
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)

from app.interface.desktop.views.report_workspace_view import (
    ReportWorkspaceView,
)


class ReportsPage(BasePage):
    """
    Reports page.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "Reports",
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        layout = QVBoxLayout(
            self,
        )

        self.workspace = (
            ReportWorkspaceView()
        )

        layout.addWidget(
            self.workspace,
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_reports(
        self,
        reports: list,
    ) -> None:
        """
        Display reports.
        """

        self.workspace.set_reports(
            reports,
        )