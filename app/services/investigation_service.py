"""
Investigation service.

Central service for managing investigations.

Responsibilities:

- create investigations
- load investigation data
- collect related objects
- prepare investigation context

Does NOT:

- perform AI analysis
- run OSINT tools
- generate reports
"""


from __future__ import annotations


from uuid import UUID

from sqlalchemy.orm import Session


from app.models.case import Case

from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.report_repository import ReportRepository


class InvestigationService:
    """
    Main investigation management service.
    """


    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self.case_repository = CaseRepository(
            session
        )

        self.evidence_repository = EvidenceRepository(
            session
        )

        self.entity_repository = EntityRepository(
            session
        )

        self.relationship_repository = RelationshipRepository(
            session
        )

        self.report_repository = ReportRepository(
            session
        )


    def create_investigation(
        self,
        title: str,
        description: str = "",
    ) -> Case:
        """
        Create new investigation case.
        """


        case = self.case_repository.create_case(
    title=title,
    description=description,
)
        self.session.commit()

        return case



    def get_investigation(
        self,
        case_id: UUID,
    ) -> Case | None:
        """
        Load investigation by id.
        """


        return self.case_repository.get(
            case_id
        )



    def get_context(
        self,
        case_id: UUID,
    ) -> dict:
        """
        Collect all investigation data.

        Used later by:
        - AI
        - reports
        - graph engine
        """


        case = self.case_repository.get(
            case_id
        )

        if case is None:
            return {}


        evidence = self.evidence_repository.get_by_case(
            case_id
        )


        entities = self.entity_repository.get_by_case(
            case_id
        )


        relationships = self.relationship_repository.get_by_case(
            case_id
        )


        reports = self.report_repository.get_by_case(
            case_id
        )


        return {
            "case": case,
            "evidence": evidence,
            "entities": entities,
            "relationships": relationships,
            "reports": reports,
        }



    def delete_investigation(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Soft delete investigation.
        """


        result = self.case_repository.delete_by_id(
            case_id
        )

        self.session.commit()

        return result