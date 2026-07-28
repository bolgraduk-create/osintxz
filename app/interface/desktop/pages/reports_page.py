"""
Reports page.

Responsible for:

- displaying investigation reports
- requesting reports from controller

Does NOT:

- generate reports
- export files
- access database
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)


class ReportsPage(BasePage):
    """
    Investigation reports page.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "Reports"
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create reports page UI.
        """

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "Investigation Reports"
        )

        layout.addWidget(
            title
        )

        self.report_list = QListWidget()

        layout.addWidget(
            self.report_list
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.clicked.connect(
            self.refresh
        )

        layout.addWidget(
            self.refresh_button
        )

    # ==========================================================
    # Refresh
    # ==========================================================

    def refresh(
        self,
    ) -> None:
        """
        Refresh reports.

        Report integration will be
        implemented later.
        """

        self.report_list.clear()

        self.report_list.addItem(
            "No reports available."
        )