"""
Timeline page.

Responsible for:

- displaying investigation timeline

Does NOT:

- execute business logic
- access database directly
"""


from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFrame,
)



class TimelinePage(QWidget):
    """
    Timeline investigation page.
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
        """
        Create page layout.
        """


        layout = QVBoxLayout(
            self
        )


        panel = QFrame()


        panel.setFrameShape(
            QFrame.Shape.StyledPanel
        )


        panel_layout = QVBoxLayout(
            panel
        )


        title = QLabel(
            "TIMELINE PAGE"
        )


        panel_layout.addWidget(
            title
        )


        layout.addWidget(
            panel
        )