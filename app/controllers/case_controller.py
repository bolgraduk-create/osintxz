"""
Case controller.

Responsible for:

- handling case actions from UI
- coordinating workspace opening
- creating investigations

Does NOT:

- access repositories
- contain business logic
- execute AI
"""

from __future__ import annotations

from uuid import UUID

from app.services.case_service import (
    CaseService,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)


class CaseController:
    """
    Desktop controller for investigations.
    """

    def __init__(
        self,
        container,
        case_service: CaseService,
        workspace_service: CaseWorkspaceService,
    ) -> None:

        self.container = container

        self.case_service = case_service

        self.workspace_service = workspace_service

    # ==========================================================
    # Cases
    # ==========================================================

    def get_cases(
        self,
    ) -> list[dict]:
        """
        Return all investigations.
        """

        cases = self.case_service.list_cases()

        return [
            {
                "id": str(case.id),
                "title": case.title,
                "description": case.description,
            }
            for case in cases
        ]

    def get_case(
        self,
        case_id: str,
    ) -> dict | None:
        """
        Return one investigation.
        """

        case = self.case_service.get_case(
            UUID(case_id)
        )

        if case is None:
            return None

        return {
            "id": str(case.id),
            "title": case.title,
            "description": case.description,
        }

    # ==========================================================
    # Workspace
    # ==========================================================

    def open_workspace(
        self,
        case_id: str,
    ) -> dict | None:
        """
        Open investigation workspace.
        """

        return self.workspace_service.get_workspace(
            case_id
        )

    # ==========================================================
    # Create
    # ==========================================================

    def create_case(
        self,
        title: str = "New Investigation",
        description: str = "",
    ) -> dict:
        """
        Create new investigation.
        """

        case = self.case_service.create_case(
            title=title,
            description=description,
        )

        return {
            "id": str(case.id),
            "title": case.title,
            "description": case.description,
        }
