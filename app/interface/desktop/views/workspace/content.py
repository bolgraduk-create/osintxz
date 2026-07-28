"""
Workspace content component.

Responsible for:

- displaying main investigation area

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFrame,
)



class WorkspaceContent(QWidget):
    """
    Main content area of workspace.
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
        Create content layout.
        """


        layout = QVBoxLayout(
            self
        )


        panel = QFrame()


        panel_layout = QVBoxLayout(
            panel
        )


        label = QLabel(
            "Investigation Area"
        )


        panel_layout.addWidget(
            label
        )


        layout.addWidget(
            panel
        )