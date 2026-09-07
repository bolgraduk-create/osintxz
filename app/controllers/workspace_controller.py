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

        super().__init__(
            container
        )

        self.workspace_service = (
            workspace_service
        )

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

        return (
            self.workspace_service
            .get_workspace(
                str(
                    case_id
                )
            )
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

    # ==========================================================
    # Workspace actions
    # ==========================================================

    def create_evidence_from_message(
        self,
        case_id,
        message_data,
    ):
        """
        Create evidence from a workspace message.
        """

        return (
            self.workspace_service
            .create_evidence_from_message(
                case_id=case_id,
                message_data=message_data,
            )
        )

    def create_entity_from_message(
        self,
        case_id,
        message_data,
        field_name,
        entity_type,
    ):
        """
        Create or reuse an entity from one message field.
        """

        return (
            self.workspace_service
            .create_entity_from_message(
                case_id=case_id,
                message_data=message_data,
                field_name=field_name,
                entity_type=entity_type,
            )
        )

    def create_timeline_from_message(
        self,
        case_id,
        message_data,
    ):
        """
        Create timeline event from a message.
        """

        return (
            self.workspace_service
            .create_timeline_from_message(
                case_id=case_id,
                message_data=message_data,
            )
        )