"""
Navigation panel.

Responsible for:

- application navigation UI
- emitting page change requests

Does NOT:

- execute business logic
- access database
"""

from __future__ import annotations


from PySide6.QtCore import (
    Signal,
)


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
)



class NavigationPanel(QWidget):
    """
    Left application navigation.
    """


    page_changed = Signal(
        str
    )



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


        buttons = {

            "Cases":
                "cases",

            "Entities":
                "entities",

            "Evidence":
                "evidence",

            "Relationships":
                "relationships",

            "Timeline":
                "timeline",

            "Reports":
                "reports",

            "AI Assistant":
                "ai",

        }



        for title, page_name in buttons.items():

            button = QPushButton(
                title
            )


            button.clicked.connect(
                lambda checked=False,
                name=page_name:
                    self.page_changed.emit(name)
            )


            layout.addWidget(
                button
            )