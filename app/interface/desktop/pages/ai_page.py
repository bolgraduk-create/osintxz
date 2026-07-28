"""
AI assistant page.

Responsible for:

- displaying AI assistant workspace
- sending requests to AI controller

Does NOT:

- execute AI models directly
- access database
- perform analysis
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)


class AIPage(BasePage):
    """
    AI assistant page.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        super().__init__(
            "AI Assistant"
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create AI page UI.
        """

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "AI Assistant Workspace"
        )

        layout.addWidget(
            title
        )

        self.question = QTextEdit()

        self.question.setPlaceholderText(
            "Ask AI about the investigation..."
        )

        layout.addWidget(
            self.question
        )

        self.ask_button = QPushButton(
            "Ask AI"
        )

        self.ask_button.clicked.connect(
            self._ask_ai
        )

        layout.addWidget(
            self.ask_button
        )

        self.answer = QTextEdit()

        self.answer.setReadOnly(
            True
        )

        layout.addWidget(
            self.answer
        )

    # ==========================================================
    # AI
    # ==========================================================

    def _ask_ai(
        self,
    ) -> None:
        """
        Send question to AI controller.
        """

        question = (
            self.question
            .toPlainText()
            .strip()
        )

        if not question:

            return

        result = (
            self.container
            .ai_controller
            .ask(
                question
            )
        )

        self.answer.setPlainText(
            result
        )