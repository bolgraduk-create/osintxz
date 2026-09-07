"""
AI workspace application service.

Responsible for:

- coordinating AI features inside workspace
- validating investigation state
- exposing AI operations to application layer

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
    Coordinates AI operations for
    a case workspace.
    """

    def __init__(
        self,
        case_service: CaseService,
    ) -> None:

        self.case_service = case_service

    # ==========================================================
    # Validation
    # ==========================================================

    def validate_case(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Ensure the case exists.
        """

        return (
            self.case_service.get_case(
                case_id
            )
            is not None
        )

    # ==========================================================
    # Case
    # ==========================================================

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

    # ==========================================================
    # Workspace state
    # ==========================================================

    def is_ready(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Returns True if the workspace
        is ready for AI analysis.
        """

        return self.validate_case(
            case_id
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict:

        return {
            "type": "ai_workspace_service",
            "version": "1.0",
        }