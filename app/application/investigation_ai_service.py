"""
Investigation AI application service.

Responsible for:

- coordinating AI analysis
- validating investigation requests
- providing a stable API for desktop application

Does NOT:

- execute models directly
- access repositories
- contain UI logic
"""

from __future__ import annotations

from uuid import UUID

from app.application.ai_workspace_service import (
    AIWorkspaceService,
)


class InvestigationAIService:
    """
    Main application service for AI operations.
    """

    def __init__(
        self,
        workspace_service: AIWorkspaceService,
    ) -> None:

        self.workspace_service = workspace_service

    def can_analyze(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Returns True if the case exists
        and is ready for AI analysis.
        """

        return self.workspace_service.validate_case(
            case_id
        )

    def get_case(
        self,
        case_id: UUID,
    ):
        """
        Return case object.
        """

        return self.workspace_service.get_case(
            case_id
        )