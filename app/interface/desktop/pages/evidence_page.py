"""
Evidence page.

Responsible for:

- displaying evidence workspace
- embedding evidence view

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

from app.interface.desktop.views.evidence_workspace_view import (
    EvidenceWorkspaceView,
)


class EvidencePage(BasePage):
    """
    Evidence page.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "Evidence",
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
            EvidenceWorkspaceView()
        )

        layout.addWidget(
            self.workspace,
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_evidence(
        self,
        evidence: list,
    ) -> None:
        """
        Display evidence.
        """

        self.workspace.set_evidence(
            evidence,
        )