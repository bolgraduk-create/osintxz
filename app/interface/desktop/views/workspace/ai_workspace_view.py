"""
AI workspace view.

Responsible for:

- displaying AI assistant
- displaying AI responses
- sending investigation questions
- emitting one-click AI workflow requests
- reacting to application language changes

Does NOT:

- execute AI
- access database
- contain business logic
"""

from __future__ import annotations

from PySide6.QtCore import (
    Signal,
)

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class AIWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Investigation AI workspace.
    """

    workflow_requested = Signal(
        str
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent,
        )

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create AI workspace interface.
        """

        self.setObjectName(
            "AIWorkspaceView"
        )

        self.layout = QVBoxLayout(
            self
        )

        self.layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        self.layout.setSpacing(
            12
        )

        # ------------------------------------------------------
        # Quick actions
        # ------------------------------------------------------

        self.actions_title = QLabel(
            self
        )

        self.actions_title.setObjectName(
            "AIWorkspaceActionsTitle"
        )

        self.layout.addWidget(
            self.actions_title
        )

        self.actions_container = QWidget(
            self
        )

        self.actions_container.setObjectName(
            "AIWorkspaceActionsContainer"
        )

        self.actions_layout = QGridLayout(
            self.actions_container
        )

        self.actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.actions_layout.setHorizontalSpacing(
            8
        )

        self.actions_layout.setVerticalSpacing(
            8
        )

        self.summary_button = self._create_action_button(
            workflow_name="investigation_summary"
        )

        self.contradictions_button = (
            self._create_action_button(
                workflow_name="contradiction_analysis"
            )
        )

        self.relationships_button = (
            self._create_action_button(
                workflow_name="relationship_analysis"
            )
        )

        self.timeline_button = (
            self._create_action_button(
                workflow_name="timeline_analysis"
            )
        )

        self.hypotheses_button = (
            self._create_action_button(
                workflow_name="hypothesis_generation"
            )
        )

        self.next_steps_button = (
            self._create_action_button(
                workflow_name="next_investigation_steps"
            )
        )

        self.actions_layout.addWidget(
            self.summary_button,
            0,
            0,
        )

        self.actions_layout.addWidget(
            self.contradictions_button,
            0,
            1,
        )

        self.actions_layout.addWidget(
            self.relationships_button,
            0,
            2,
        )

        self.actions_layout.addWidget(
            self.timeline_button,
            1,
            0,
        )

        self.actions_layout.addWidget(
            self.hypotheses_button,
            1,
            1,
        )

        self.actions_layout.addWidget(
            self.next_steps_button,
            1,
            2,
        )

        self.layout.addWidget(
            self.actions_container
        )

        # ------------------------------------------------------
        # Chat history
        # ------------------------------------------------------

        self.chat = QTextEdit(
            self
        )

        self.chat.setObjectName(
            "aiChat"
        )

        self.chat.setReadOnly(
            True
        )

        self.layout.addWidget(
            self.chat,
            1,
        )

        # ------------------------------------------------------
        # Prompt input
        # ------------------------------------------------------

        self.prompt = QTextEdit(
            self
        )

        self.prompt.setObjectName(
            "aiPrompt"
        )

        self.prompt.setMaximumHeight(
            120
        )

        self.layout.addWidget(
            self.prompt
        )

        self.ask_button = QPushButton(
            self
        )

        self.ask_button.setObjectName(
            "aiAnalyzeButton"
        )

        self.layout.addWidget(
            self.ask_button
        )

    def _create_action_button(
        self,
        *,
        workflow_name: str,
    ) -> QPushButton:
        """
        Create one AI workflow button.
        """

        button = QPushButton(
            self.actions_container
        )

        button.setProperty(
            "workflow_name",
            workflow_name,
        )

        button.clicked.connect(
            lambda checked=False, name=workflow_name:
                self.workflow_requested.emit(
                    name
                )
        )

        return button

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        self.actions_title.setText(
            self.translate(
                "ai_workspace.actions.title",
                default="Quick analysis",
            )
        )

        self.summary_button.setText(
            self.translate(
                "ai_workspace.actions.summary",
                default="Investigation summary",
            )
        )

        self.contradictions_button.setText(
            self.translate(
                "ai_workspace.actions.contradictions",
                default="Find contradictions",
            )
        )

        self.relationships_button.setText(
            self.translate(
                "ai_workspace.actions.relationships",
                default="Analyze relationships",
            )
        )

        self.timeline_button.setText(
            self.translate(
                "ai_workspace.actions.timeline",
                default="Analyze timeline",
            )
        )

        self.hypotheses_button.setText(
            self.translate(
                "ai_workspace.actions.hypotheses",
                default="Generate hypotheses",
            )
        )

        self.next_steps_button.setText(
            self.translate(
                "ai_workspace.actions.next_steps",
                default="Recommend next steps",
            )
        )

        self.prompt.setPlaceholderText(
            self.translate(
                "ai_workspace.prompt.placeholder",
                default=(
                    "Ask AI about this investigation..."
                ),
            )
        )

        self.ask_button.setText(
            self.translate(
                "ai_workspace.action.analyze",
                default="Analyze",
            )
        )

        self.ask_button.setToolTip(
            self.translate(
                "ai_workspace.action.analyze_tooltip",
                default=(
                    "Send the current question "
                    "to the AI assistant"
                ),
            )
        )

    # ==========================================================
    # State
    # ==========================================================

    def set_loading(
        self,
        loading: bool,
    ) -> None:
        """
        Enable or disable AI controls.
        """

        enabled = not loading

        self.prompt.setEnabled(
            enabled
        )

        self.ask_button.setEnabled(
            enabled
        )

        for button in (
            self.summary_button,
            self.contradictions_button,
            self.relationships_button,
            self.timeline_button,
            self.hypotheses_button,
            self.next_steps_button,
        ):

            button.setEnabled(
                enabled
            )

        if loading:

            self.ask_button.setText(
                self.translate(
                    "ai_workspace.action.processing",
                    default="Analyzing...",
                )
            )

        else:

            self.retranslate_ui()

    # ==========================================================
    # Output
    # ==========================================================

    def append_response(
        self,
        text: str,
    ) -> None:
        """
        Append an AI response to the chat.
        """

        normalized_text = str(
            text
            or ""
        ).strip()

        if not normalized_text:

            return

        self.chat.append(
            normalized_text
        )

    def clear(
        self,
    ) -> None:
        """
        Clear the AI conversation and prompt.
        """

        self.chat.clear()

        self.prompt.clear()