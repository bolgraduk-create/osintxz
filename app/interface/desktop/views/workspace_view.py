"""
Main workspace view.

Responsible for:

- displaying investigation workspace
- combining workspace components

Does NOT:

- execute business logic
- access database directly
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)


from app.interface.desktop.views.workspace.header import (
    WorkspaceHeader,
)


from app.interface.desktop.views.workspace.content import (
    WorkspaceContent,
)


from app.interface.desktop.views.workspace.status import (
    WorkspaceStatus,
)



class WorkspaceView(QWidget):
    """
    Main investigation workspace.
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
        Create workspace layout.
        """


        layout = QVBoxLayout(
            self
        )


        header = WorkspaceHeader()


        content = WorkspaceContent()


        status = WorkspaceStatus()



        layout.addWidget(
            header
        )


        layout.addWidget(
            content
        )


        layout.addWidget(
            status
        )