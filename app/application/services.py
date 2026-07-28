"""
Application services.

Provides application-level entry points.

Responsibilities:

- coordinate application workflow
- manage investigation execution
- connect domain services

Does NOT:

- perform analysis
- call AI directly
- access database
- replace domain services
"""

from __future__ import annotations


from typing import Any


from app.application.workflow import (
    InvestigationWorkflow,
)


from app.application.case_workspace_service import (
    CaseWorkspaceService,
)


from app.services.case_service import (
    CaseService,
)



class InvestigationApplicationService:
    """
    Main application service
    for investigation execution.
    """



    def __init__(
        self,
        workflow: InvestigationWorkflow | None = None,
        case_service: CaseService | None = None,
        workspace_service: CaseWorkspaceService | None = None,
    ):

        self.workflow = (
            workflow
            or InvestigationWorkflow()
        )


        self.case_service = (
            case_service
        )


        self.workspace_service = (
            workspace_service
            or CaseWorkspaceService(
                case_service
            )
        )



    # ==========================================================
    # Execution
    # ==========================================================

    def execute_investigation(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute investigation workflow.
        """


        if self.case_service is not None:

            case = self.case_service.create_case(
                title=data.get(
                    "title",
                    "New Investigation",
                ),
                description=data.get(
                    "description"
                ),
            )


            data["case_id"] = str(
                case.id
            )



        return self.workflow.execute(
            data
        )



    # ==========================================================
    # Cases
    # ==========================================================

    def list_cases(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return investigation cases.
        """


        if self.case_service is None:

            return []


        cases = (
            self.case_service.list_cases()
        )


        return [

            {
                "id":
                    str(case.id),

                "title":
                    case.title,

                "description":
                    case.description,

            }

            for case in cases

        ]



    def get_case(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Return single investigation case.
        """


        if self.case_service is None:

            return None



        case = (
            self.case_service.get_case(
                case_id
            )
        )


        if case is None:

            return None



        return {

            "id":
                str(case.id),

            "title":
                case.title,

            "description":
                case.description,

        }



    # ==========================================================
    # Workspace
    # ==========================================================

    def get_case_workspace(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Return full case workspace.
        """


        return (
            self.workspace_service
            .get_workspace(
                case_id
            )
        )



    # ==========================================================
    # Workflow configuration
    # ==========================================================

    def add_step(
        self,
        step,
    ) -> None:
        """
        Add workflow step.
        """


        self.workflow.add_step(
            step
        )



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Service metadata.
        """


        return {

            "type":
                "investigation_application_service",

            "version":
                "1.0",

        }