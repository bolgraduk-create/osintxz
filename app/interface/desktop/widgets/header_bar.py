"""
Application header bar.

Responsible for:

- displaying application title
- displaying top information

Does NOT:

- execute logic
- access services
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
)



class HeaderBar(QWidget):
    """
    Top application header.
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

        layout = QHBoxLayout(
            self
        )


        title = QLabel(
            "OSINT Intelligence Platform"
        )


        version = QLabel(
            "v0.1.0"
        )


        layout.addWidget(
            title
        )


        layout.addStretch()


        layout.addWidget(
            version
        )