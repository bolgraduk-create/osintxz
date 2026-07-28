"""
Application status bar.

Responsible for:

- displaying application status
- displaying system information

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



class StatusBar(QWidget):
    """
    Bottom application status panel.
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


        self.status_label = QLabel(
            "Ready"
        )


        self.database_label = QLabel(
            "Database: Connected"
        )


        self.version_label = QLabel(
            "Version: 0.1.0"
        )


        layout.addWidget(
            self.status_label
        )


        layout.addStretch()


        layout.addWidget(
            self.database_label
        )


        layout.addWidget(
            self.version_label
        )