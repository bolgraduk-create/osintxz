"""
Application services.

Provides application-level entry points.

Responsibilities:

- coordinate application workflow
- manage investigation execution
- provide access to application workspaces
- connect application-level services

Does NOT:

- perform domain analysis
- call AI providers directly
- access database
- replace domain services
- contain UI logic
"""

from __future__ import annotations

from typing import Any

from app.application.workflow import (
    InvestigationWorkflow,
)

from app.application.workspaces import (
    ApplicationWorkspaces,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)

from app.application.ai_workspace_service import (
    AIWorkspaceService,
)

from app.application.import_workspace_service import (
    ImportWorkspaceService,
)

from app.application.investigation_ai_service import (
    InvestigationAIService,
)


class InvestigationApplicationService:
    """
    Main application facade.

    Coordinates the main investigation workflow and provides
    stable application-level access to registered workspaces.

    New code should inject ``ApplicationWorkspaces``.

    Legacy individual workspace arguments are temporarily
    supported so the Composition Root can be migrated safely.
    """

    def __init__(
        self,
        workflow: InvestigationWorkflow,
        investigation_ai_service: InvestigationAIService,
        workspaces: ApplicationWorkspaces | None = None,
        workspace_service: CaseWorkspaceService | None = None,
        ai_workspace_service: AIWorkspaceService | None = None,
        import_workspace_service: ImportWorkspaceService | None = None,
    ) -> None:

        self.workflow = workflow

        self.investigation_ai_service = (
            investigation_ai_service
        )

        self.workspaces = self._resolve_workspaces(
            workspaces=workspaces,
            workspace_service=workspace_service,
            ai_workspace_service=(
                ai_workspace_service
            ),
            import_workspace_service=(
                import_workspace_service
            ),
        )

        # ======================================================
        # Temporary compatibility aliases
        # ======================================================
        #
        # Existing controllers and other application modules
        # may still access these old attributes.
        #
        # They will be removed only after all callers migrate
        # to self.workspaces.
        # ======================================================

        self.workspace_service = (
            self.workspaces.case
        )

        self.ai_workspace_service = (
            self.workspaces.ai
        )

        self.import_workspace_service = (
            self.workspaces.imports
        )

    # ==========================================================
    # Workflow
    # ==========================================================

    def execute(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute the main application workflow.
        """

        return self.workflow.execute(
            data
        )

    # ==========================================================
    # Case workspace
    # ==========================================================

    def workspace(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Return complete workspace data for a case.
        """

        return self.workspaces.case.get_workspace(
            case_id
        )

    # ==========================================================
    # AI workspace
    # ==========================================================

    def can_analyze(
        self,
        case_id: str,
    ) -> bool:
        """
        Check whether a case can be analyzed.
        """

        return self.workspaces.ai.validate_case(
            case_id
        )

    # ==========================================================
    # Import workspace
    # ==========================================================

    def import_telegram(
        self,
        case_id: str,
        export_path: str,
    ) -> None:
        """
        Import a Telegram export into a case.
        """

        self.workspaces.imports.import_telegram(
            case_id,
            export_path,
        )

    # ==========================================================
    # Workspace access
    # ==========================================================

    def get_workspace_service(
        self,
        workspace_name: str,
    ) -> Any | None:
        """
        Return a registered workspace service by name.
        """

        return self.workspaces.get(
            workspace_name
        )

    def workspace_names(
        self,
    ) -> list[str]:
        """
        Return registered workspace names.
        """

        return self.workspaces.names()

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return application service metadata.
        """

        workspace_metadata = (
            self.workspaces.metadata()
        )

        return {
            "type": (
                "investigation_application_service"
            ),
            "version": "3.0",
            "workspaces": workspace_metadata,
        }

    # ==========================================================
    # Dependency resolution
    # ==========================================================

    def _resolve_workspaces(
        self,
        workspaces: ApplicationWorkspaces | None,
        workspace_service: CaseWorkspaceService | None,
        ai_workspace_service: AIWorkspaceService | None,
        import_workspace_service: ImportWorkspaceService | None,
    ) -> ApplicationWorkspaces:
        """
        Resolve the workspace container.

        Prefer an already-created ApplicationWorkspaces
        instance. Legacy separate workspace services are
        supported during the migration period.
        """

        if workspaces is not None:
            return workspaces

        missing_services: list[str] = []

        if workspace_service is None:
            missing_services.append(
                "workspace_service"
            )

        if ai_workspace_service is None:
            missing_services.append(
                "ai_workspace_service"
            )

        if import_workspace_service is None:
            missing_services.append(
                "import_workspace_service"
            )

        if missing_services:

            missing_names = ", ".join(
                missing_services
            )

            raise ValueError(
                "ApplicationWorkspaces was not provided "
                "and legacy workspace dependencies are "
                f"missing: {missing_names}."
            )

        return ApplicationWorkspaces(
            case_workspace=workspace_service,
            ai_workspace=ai_workspace_service,
            import_workspace=(
                import_workspace_service
            ),
        )