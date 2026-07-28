"""
OSINT investigation service.

Connects OSINT pipeline with
the investigation domain.

Responsibilities:

- execute OSINT investigation
- create source records
- store evidence candidates
- store entity candidates

Does NOT:

- execute external tools directly
- call AI
- resolve entities
- build relationships
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.source import SourceType
from app.models.evidence import EvidenceType
from app.models.entity import EntityType

from app.osint.models import ConnectorRequest
from app.osint.pipeline import OsintPipeline
from app.osint.result_mapper import ResultMapper

from app.services.source_service import SourceService
from app.services.evidence_service import EvidenceService
from app.services.entity_service import EntityService


class OsintInvestigationService:
    """
    Service connecting OSINT
    with investigation cases.
    """

    def __init__(
        self,
        session: Session,
        pipeline: OsintPipeline,
    ) -> None:

        self.pipeline = pipeline

        self.mapper = ResultMapper()

        self.source_service = SourceService(
            session
        )

        self.evidence_service = EvidenceService(
            session
        )

        self.entity_service = EntityService(
            session
        )


    def run_investigation(
        self,
        case_id: UUID,
        request: ConnectorRequest,
    ) -> dict:
        """
        Execute OSINT collection
        and save results.
        """

        source = self.source_service.create_source(

            case_id=case_id,

            name=(
                f"OSINT: "
                f"{request.target.value}"
            ),

            source_type=SourceType.API,

            description=(
                "OSINT connector investigation"
            ),
        )


        results = self.pipeline.run(
            request
        )


        saved_evidence = 0
        saved_entities = 0


        for result in results:

            if not result.success:
                continue


            mapped = self.mapper.map(
                result
            )


            for evidence in mapped.evidence:

                self.evidence_service.create_evidence(

                    case_id=case_id,

                    source_id=source.id,

                    evidence_type=(
                        self._map_evidence_type(
                            evidence.category
                        )
                    ),

                    title=(
                        f"{result.connector} "
                        f"finding"
                    ),

                    value=evidence.value,

                    description=(
                        evidence.source
                    ),
                )

                saved_evidence += 1



            for entity in mapped.entities:

                self.entity_service.create_entity(

                    case_id=case_id,

                    entity_type=(
                        self._map_entity_type(
                            entity.entity_type
                        )
                    ),

                    value=entity.value,

                    confidence=entity.confidence,

                    metadata_json=json.dumps(
                        entity.metadata,
                        default=str,
                    ),
                )

                saved_entities += 1


        return {

            "source_id": str(source.id),

            "connectors_executed": len(
                results
            ),

            "evidence_created": saved_evidence,

            "entities_created": saved_entities,

        }


    def _map_entity_type(
        self,
        value: str,
    ) -> EntityType:
        """
        Convert connector category
        into platform entity type.
        """

        try:

            return EntityType(
                value.lower()
            )

        except ValueError:

            return EntityType.OTHER



    def _map_evidence_type(
        self,
        value: str,
    ) -> EvidenceType:
        """
        Convert connector category
        into evidence type.
        """

        try:

            return EvidenceType(
                value.lower()
            )

        except ValueError:

            return EvidenceType.OTHER