"""
Relationship workspace view.

Responsible for:

- displaying entity relationships

Does NOT:

- access database
- execute business logic
- analyze relationships
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
)



class RelationshipWorkspaceView(QWidget):
    """
    Relationship tab workspace.
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
        Create relationship UI.
        """


        layout = QVBoxLayout(
            self
        )


        self.title = QLabel(
            "Relationships"
        )


        layout.addWidget(
            self.title
        )


        self.list = QListWidget()


        layout.addWidget(
            self.list
        )



    # ==========================================================
    # Data
    # ==========================================================

    def set_relationships(
        self,
        relationships: list,
    ) -> None:
        """
        Display relationships.
        """


        self.list.clear()


        for relationship in relationships:

            text = (

                f"{relationship['type']} | "

                f"{relationship['source']} → "

                f"{relationship['target']}"

            )


            self.list.addItem(
                text
            )