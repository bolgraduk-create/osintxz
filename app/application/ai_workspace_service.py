"""
AI workspace application service.

Responsible for:

- coordinating AI features inside workspace
- providing AI operations for a Case
- delegating work to AI layer

Does NOT:

- execute AI models directly
- access repositories
- contain UI logic
"""

from __future__ import annotations

from uuid import UUID

from app.services.case_service import CaseService


class AIWorkspaceService:
    """
    Coordinates AI operations for a case workspace.
    """

    def __init__(
        self,
        case_service: CaseService,
    ) -> None:

        self.case_service = case_service

    def validate_case(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Ensure that a case exists before
        running AI operations.
        """

        case = self.case_service.get_case(
            case_id
        )

        return case is not None

    def get_case(
        self,
        case_id: UUID,
    ):
        """
        Return case object.
        """

        return self.case_service.get_case(
            case_id
        )