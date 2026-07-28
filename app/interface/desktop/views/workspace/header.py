"""
Workspace header component.

Responsible for:

- displaying workspace title
- displaying investigation context

Does NOT:

- execute actions
- access database
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
)



class WorkspaceHeader(QWidget):
    """
    Header section of investigation workspace.
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
        Create header layout.
        """


        layout = QHBoxLayout(
            self
        )


        title = QLabel(
            "Investigation Workspace"
        )


        layout.addWidget(
            title
        )