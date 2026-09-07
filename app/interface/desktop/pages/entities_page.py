"""
Entities page.

Responsible for:

- displaying entity workspace
- embedding entity view

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

from app.interface.desktop.views.entity_workspace_view import (
    EntityWorkspaceView,
)


class EntitiesPage(BasePage):
    """
    Entities page.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "Entities",
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
            EntityWorkspaceView()
        )

        layout.addWidget(
            self.workspace,
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_entities(
        self,
        entities: list,
    ) -> None:
        """
        Display entities.
        """

        self.workspace.set_entities(
            entities,
        )