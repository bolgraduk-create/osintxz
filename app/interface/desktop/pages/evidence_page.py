"""
Evidence page.

Responsible for:

- displaying evidence workspace
- requesting evidence from controller

Does NOT:

- execute business logic
- access database
- call services directly
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


class EvidencePage(BasePage):
    """
    Evidence workspace.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "Evidence"
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "Evidence Workspace"
        )

        layout.addWidget(
            title
        )

        self.evidence_list = QListWidget()

        layout.addWidget(
            self.evidence_list
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.clicked.connect(
            self.refresh
        )

        layout.addWidget(
            self.refresh_button)

    # ==========================================================
    # Refresh
    # ==========================================================

    def refresh(
        self,
    ) -> None:
        """
        Refresh evidence list.

        Evidence integration will be
        implemented in the next stage.
        """

        self.evidence_list.clear()

        self.evidence_list.addItem(
            "No evidence loaded."
        )