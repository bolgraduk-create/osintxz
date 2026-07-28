"""
Relationships page.

Responsible for:

- displaying relationship analysis workspace

Does NOT:

- perform analysis
- access database
- call services
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)



class RelationshipsPage(QWidget):
    """
    Relationships workspace.
    """


    def __init__(self, container):
        super().__init__()
        self.container = container
        self._setup_ui()

    def _setup_ui(
        self,
    ) -> None:

        layout = QVBoxLayout(
            self
        )


        title = QLabel(
            "Relationships Analysis"
        )


        layout.addWidget(
            title
        )