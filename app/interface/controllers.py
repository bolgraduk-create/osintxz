"""
Application controllers.

Connect interface layer
with application services.

Does NOT contain
business logic.
"""

from __future__ import annotations


from typing import Any


from app.application.services import (
    InvestigationApplicationService,
)



class InvestigationController:
    """
    Controller for investigation requests.
    """



    def __init__(
        self,
        service: InvestigationApplicationService,
    ):

        self.service = service



    # ==========================================================
    # Investigation
    # ==========================================================

    def create_investigation(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Start investigation workflow.
        """


        return (
            self.service.execute_investigation(
                data
            )
        )



    # ==========================================================
    # Cases
    # ==========================================================

    def get_cases(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return investigation cases.
        """


        return (
            self.service.list_cases()
        )



    def get_case(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Return single investigation case.
        """


        return (
            self.service.get_case(
                case_id
            )
        )



    # ==========================================================
    # Case workspace
    # ==========================================================

    def get_case_workspace(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Return case workspace data.
        """


        return (
            self.service
            .get_case_workspace(
                case_id
            )
        )



    # ==========================================================
    # Generic handler
    # ==========================================================

    def handle(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generic request handler.
        """


        return self.create_investigation(
            request
        )