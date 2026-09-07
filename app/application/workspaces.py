"""
Application workspace container.

Groups application-level workspace services
behind one stable access point.

Responsibilities:

- provide access to workspace services
- keep workspace dependencies organized
- provide a stable workspace API
- support workspace extensions

Does NOT:

- execute application workflows
- contain business logic
- access database
- create services
- call AI directly
"""

from __future__ import annotations

from typing import Any

from app.application.ai_workspace_service import (
    AIWorkspaceService,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)

from app.application.import_workspace_service import (
    ImportWorkspaceService,
)

from app.application.osint_workspace_service import (
    OsintWorkspaceService,
)


class ApplicationWorkspaces:
    """
    Container for application workspace services.

    Provides grouped access to all registered
    application workspace services.

    Example:

        workspaces.case.get_workspace(...)
        workspaces.ai.validate_case(...)
        workspaces.imports.import_telegram(...)
        workspaces.osint.run_investigation(...)
    """

    def __init__(
        self,
        case_workspace: CaseWorkspaceService,
        ai_workspace: AIWorkspaceService,
        import_workspace: ImportWorkspaceService,
        osint_workspace: OsintWorkspaceService | None = None,
    ) -> None:

        self.case = case_workspace

        self.ai = ai_workspace

        self.imports = import_workspace

        self.osint = osint_workspace

    # ==========================================================
    # Workspace access
    # ==========================================================

    def get(
        self,
        workspace_name: str,
    ) -> Any | None:
        """
        Return a workspace service by name.
        """

        normalized_name = (
            str(
                workspace_name
            )
            .strip()
            .lower()
        )

        workspace_map = {
            "case": self.case,
            "ai": self.ai,
            "import": self.imports,
            "imports": self.imports,
            "osint": self.osint,
        }

        return workspace_map.get(
            normalized_name
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def names(
        self,
    ) -> list[str]:
        """
        Return names of registered workspaces.
        """

        workspace_names = [
            "case",
            "ai",
            "imports",
        ]

        if self.osint is not None:

            workspace_names.append(
                "osint"
            )

        return workspace_names

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return workspace container metadata.
        """

        names = self.names()

        return {
            "type": "application_workspaces",
            "count": len(
                names
            ),
            "names": names,
            "osint_available": (
                self.osint is not None
            ),
        }

    # ==========================================================
    # Validation
    # ==========================================================

    def require(
        self,
        workspace_name: str,
    ) -> Any:
        """
        Return a registered workspace.

        Raise a clear error when the requested workspace
        is unavailable.
        """

        workspace = self.get(
            workspace_name
        )

        if workspace is None:

            raise LookupError(
                "Application workspace is not "
                f"registered: {workspace_name}"
            )

        return workspace

    def __contains__(
        self,
        workspace_name: str,
    ) -> bool:
        """
        Check whether a workspace is registered.
        """

        return (
            self.get(
                workspace_name
            )
            is not None
        )

    def __len__(
        self,
    ) -> int:
        """
        Return number of registered workspaces.
        """

        return len(
            self.names()
        )