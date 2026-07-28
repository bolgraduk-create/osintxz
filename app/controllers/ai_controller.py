"""
AI controller.

Bridge between desktop UI
and AI application layer.

Responsible for:

- starting AI analysis
- asking investigation questions
- validating AI availability

Does NOT:

- execute AI models
- access repositories
- contain UI logic
"""

from __future__ import annotations

from uuid import UUID

from app.controllers.base_controller import (
    BaseController,
)

from app.application.investigation_ai_service import (
    InvestigationAIService,
)


class AIController(BaseController):
    """
    Desktop AI controller.
    """

    def __init__(
        self,
        container,
        ai_service: InvestigationAIService,
    ) -> None:

        super().__init__(container)

        self.ai_service = ai_service

    # ==========================================================
    # Validation
    # ==========================================================

    def can_analyze(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Check whether analysis can start.
        """

        return self.ai_service.can_analyze(
            case_id
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

        return self.ai_service.get_case(
            case_id
        )