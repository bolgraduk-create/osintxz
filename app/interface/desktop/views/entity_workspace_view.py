"""
Entity workspace view.

Responsible for:

- displaying extracted entities

Does NOT:

- access database
- execute business logic
- resolve entities
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
)



class EntityWorkspaceView(QWidget):
    """
    Entity tab workspace.
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


        layout = QVBoxLayout(
            self
        )


        self.title = QLabel(
            "Entities"
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

    def set_entities(
        self,
        entities: list,
    ) -> None:
        """
        Display entities.
        """


        self.list.clear()


        for entity in entities:

            text = (

                f"{entity['type']} | "

                f"{entity['value']}"

            )


            self.list.addItem(
                text
            )