"""
Workspace controller.

Bridge between desktop workspace UI
and application layer.

Responsible for:

- loading workspace
- refreshing workspace
- exposing workspace operations

Does NOT:

- access repositories
- execute SQL
- contain UI logic
"""

from __future__ import annotations

from app.controllers.base_controller import (
    BaseController,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)


class WorkspaceController(BaseController):
    """
    Controller for Case Workspace.
    """

    def __init__(
        self,
        container,
        workspace_service: CaseWorkspaceService,
    ) -> None:

        super().__init__(container)

        self.workspace_service = workspace_service

    # ==========================================================
    # Workspace
    # ==========================================================

    def load_workspace(
        self,
        case_id,
    ):
        """
        Load workspace information.
        """

        return self.workspace_service.get_workspace(
            str(case_id)
        )

    def refresh_workspace(
        self,
        case_id,
    ):
        """
        Refresh workspace.
        """

        return self.load_workspace(
            case_id
        )