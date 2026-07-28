"""
Workspace status component.

Responsible for:

- displaying workspace status information

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
)



class WorkspaceStatus(QWidget):
    """
    Status bar for workspace.
    """



    def __init__(
        self,
    ):

        super().__init__()


        self._setup_ui()



    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create status layout.
        """


        layout = QHBoxLayout(
            self
        )


        status = QLabel(
            "Ready"
        )


        layout.addWidget(
            status
        )