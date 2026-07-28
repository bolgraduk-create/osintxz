"""
Timeline workspace view.

Responsible for:

- displaying investigation timeline events

Does NOT:

- access database
- execute business logic
- analyze events
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
)



class TimelineWorkspaceView(QWidget):
    """
    Timeline tab workspace.
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
        Create timeline UI.
        """


        layout = QVBoxLayout(
            self
        )


        self.title = QLabel(
            "Timeline"
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

    def set_events(
        self,
        events: list,
    ) -> None:
        """
        Display timeline events.
        """


        self.list.clear()


        for event in events:

            text = (

                f"{event.get('date', '')} | "

                f"{event.get('title', '')}"

            )


            self.list.addItem(
                text
            )