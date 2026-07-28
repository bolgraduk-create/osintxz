"""
AI analysis controller.

Responsible for:

- receiving UI requests
- validating user actions
- delegating AI operations

Does NOT:

- execute AI models
- access database
- contain business logic
"""

from __future__ import annotations

from uuid import UUID

from app.application.investigation_ai_service import (
    InvestigationAIService,
)

from app.ai.analysis.ai_analyzer import (
    AIAnalyzer,
)


class AIAnalysisController:
    """
    Controller for AI operations.
    """

    def __init__(
        self,
        investigation_service: InvestigationAIService,
        analyzer: AIAnalyzer,
    ) -> None:

        self.investigation_service = (
            investigation_service
        )

        self.analyzer = analyzer

    # ==========================================================
    # Validation
    # ==========================================================

    def can_analyze(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Check whether analysis
        can be started.
        """

        return (
            self.investigation_service
            .can_analyze(
                case_id
            )
        )

    # ==========================================================
    # Case
    # ==========================================================

    def get_case(
        self,
        case_id: UUID,
    ):
        """
        Return case.
        """

        return (
            self.investigation_service
            .get_case(
                case_id
            )
        )

    # ==========================================================
    # AI
    # ==========================================================

    def ask(
        self,
        question: str,
    ) -> str:
        """
        Ask AI assistant.
        """

        result = (
            self.analyzer.ask(
                question
            )
        )

        return result.get(
            "response",
            "",
        )

    def analyze_case(
        self,
        case: dict,
    ) -> str:
        """
        Analyze case.
        """

        result = (
            self.analyzer.analyze_case(
                case
            )
        )

        return result.get(
            "response",
            "",
        )

    def analyze_document(
        self,
        document: dict,
    ) -> str:
        """
        Analyze document.
        """

        result = (
            self.analyzer.analyze_document(
                document
            )
        )

        return result.get(
            "response",
            "",
        )

    def analyze_messages(
        self,
        messages: list[dict],
    ) -> str:
        """
        Analyze messages.
        """

        result = (
            self.analyzer.analyze_messages(
                messages
            )
        )

        return result.get(
            "response",
            "",
        )