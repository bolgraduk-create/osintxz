"""
Case controller.

Responsible for:

- handling case actions from UI
- coordinating workspace opening
- creating investigations
- controlling UI transaction boundaries

Does NOT:

- access repositories
- contain domain business logic
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
        case_id: str | UUID,
    ) -> dict | None:
        """
        Return one investigation.
        """

        normalized_case_id = (
            case_id
            if isinstance(case_id, UUID)
            else UUID(str(case_id))
        )

        case = self.case_service.get_case(
            normalized_case_id
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
        Create and commit a new investigation.
        """

        try:

            case = self.case_service.create_case(
                title=title,
                description=description,
            )

            self.container.commit()

            return {
                "id": str(case.id),
                "title": case.title,
                "description": case.description,
            }

        except Exception:

            self.container.rollback()

            raise

            # ==========================================================
    # Delete
    # ==========================================================

    def delete_case(
        self,
        case_id: str | UUID,
    ) -> bool:
        """
        Soft delete and commit one investigation.
        """

        try:

            normalized_case_id = (
                case_id
                if isinstance(
                    case_id,
                    UUID,
                )
                else UUID(
                    str(
                        case_id
                    )
                )
            )

            deleted = (
                self.case_service
                .delete_case(
                    normalized_case_id
                )
            )

            if not deleted:

                return False

            self.container.commit()

            return True

        except Exception:

            self.container.rollback()

            raise

    # ==========================================================
    # Rename
    # ==========================================================

    def rename_case(
        self,
        case_id: str | UUID,
        new_title: str,
    ) -> bool:
        """
        Rename investigation.
        """

        try:

            normalized_case_id = (
                case_id
                if isinstance(
                    case_id,
                    UUID,
                )
                else UUID(
                    str(case_id)
                )
            )

            renamed = (
                self.case_service.rename_case(
                    normalized_case_id,
                    new_title,
                )
            )

            if not renamed:

                return False

            self.container.commit()

            return True

        except Exception:

            self.container.rollback()

            raise