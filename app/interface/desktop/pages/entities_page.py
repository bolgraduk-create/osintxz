"""
Entities page.

Responsible for:

- displaying entity workspace

Does NOT:

- execute business logic
- access database
- call services directly
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)



class EntitiesPage(QWidget):
    """
    Entities workspace.
    """



    def __init__(
        self,
        container,
    ):

        super().__init__()


        self.container = container


        self._setup_ui()



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
            "Entities Workspace"
        )


        layout.addWidget(
            title
        )