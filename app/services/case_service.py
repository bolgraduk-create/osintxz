"""
Case service.

Contains business logic related
to investigation cases.

Services must use repositories
and never access database directly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.case import Case
from app.repositories.case_repository import CaseRepository



class CaseService:
    """
    Service for investigation cases.
    """



    def __init__(
        self,
        session: Session,
    ):

        self.repository = CaseRepository(
            session
        )



    def create_case(
        self,
        title: str,
        project_id: UUID | None = None,
        description: str | None = None,
    ) -> Case:
        """
        Create new investigation case.
        """


        case = Case(
            title=title,
            project_id=project_id,
            description=description,
        )


        return self.repository.create(
            case
        )



    def get_case(
        self,
        case_id: UUID,
    ) -> Case | None:
        """
        Get case by id.
        """


        return self.repository.get(
            case_id
        )



    def get_case_by_title(
        self,
        title: str,
    ) -> Case | None:
        """
        Find case by title.
        """


        return self.repository.get_by_title(
            title
        )



    def list_cases(
        self,
    ) -> list[Case]:
        """
        Return all active cases.
        """


        return self.repository.get_active_cases()

    def get_cases(
        self,
    ) -> list[Case]:
        """
        Return all active cases.

        Compatibility method for controllers.
        """

        return self.list_cases()



    def delete_case(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Soft delete case.
        """


        return self.repository.delete_by_id(
            case_id
        )