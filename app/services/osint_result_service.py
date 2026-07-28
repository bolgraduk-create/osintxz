"""
OSINT result service.

Provides access to OSINT investigation results
stored inside the investigation domain.

Responsibilities:

- retrieve OSINT sources
- retrieve OSINT evidence
- retrieve OSINT entities
- filter results by connector/source

Does NOT:

- execute connectors
- call AI
- create OSINT data
- resolve entities
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.source import Source
from app.models.evidence import Evidence
from app.models.entity import Entity

from app.repositories.source_repository import SourceRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.entity_repository import EntityRepository


class OsintResultService:
    """
    Service for accessing stored OSINT results.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.source_repository = SourceRepository(
            session
        )

        self.evidence_repository = EvidenceRepository(
            session
        )

        self.entity_repository = EntityRepository(
            session
        )


    def get_case_sources(
        self,
        case_id: UUID,
    ) -> list[Source]:
        """
        Return OSINT sources
        belonging to a case.
        """

        return self.source_repository.get_by_case(
            case_id
        )


    def get_case_evidence(
        self,
        case_id: UUID,
    ) -> list[Evidence]:
        """
        Return all OSINT evidence
        belonging to a case.
        """

        return self.evidence_repository.get_by_case(
            case_id
        )


    def get_case_entities(
        self,
        case_id: UUID,
    ) -> list[Entity]:
        """
        Return all OSINT entities
        belonging to a case.
        """

        return self.entity_repository.get_by_case(
            case_id
        )


    def get_source_evidence(
        self,
        source_id: UUID,
    ) -> list[Evidence]:
        """
        Return evidence produced
        by specific OSINT source.
        """

        return self.evidence_repository.get_by_source(
            source_id
        )


    def get_evidence_by_type(
        self,
        case_id: UUID,
        evidence_type,
    ) -> list[Evidence]:
        """
        Filter evidence by type.
        """

        evidence = self.get_case_evidence(
            case_id
        )

        return [
            item
            for item in evidence
            if item.evidence_type == evidence_type
        ]


    def get_entities_by_type(
        self,
        case_id: UUID,
        entity_type,
    ) -> list[Entity]:
        """
        Filter entities by type.
        """

        entities = self.get_case_entities(
            case_id
        )

        return [
            item
            for item in entities
            if item.entity_type == entity_type
        ]


    def build_summary(
        self,
        case_id: UUID,
    ) -> dict:
        """
        Create compact OSINT result summary.
        """

        sources = self.get_case_sources(
            case_id
        )

        evidence = self.get_case_evidence(
            case_id
        )

        entities = self.get_case_entities(
            case_id
        )


        return {

            "sources": len(
                sources
            ),

            "evidence": len(
                evidence
            ),

            "entities": len(
                entities
            ),

        }