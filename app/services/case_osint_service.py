"""
Case OSINT service.

Provides OSINT information
attached to investigation cases.

Responsibilities:

- collect OSINT statistics
- provide case OSINT overview
- combine OSINT sources,
  evidence and entities

Does NOT:

- execute connectors
- store data
- call AI
"""

from __future__ import annotations

from uuid import UUID

from app.services.osint_result_service import (
    OsintResultService,
)


class CaseOsintService:
    """
    Service for OSINT case overview.
    """

    def __init__(
        self,
        osint_result_service: OsintResultService,
    ) -> None:

        self.osint_result_service = (
            osint_result_service
        )


    def get_overview(
        self,
        case_id: UUID,
    ) -> dict:
        """
        Return complete OSINT overview
        for investigation case.
        """

        sources = (
            self.osint_result_service
            .get_case_sources(
                case_id
            )
        )

        evidence = (
            self.osint_result_service
            .get_case_evidence(
                case_id
            )
        )

        entities = (
            self.osint_result_service
            .get_case_entities(
                case_id
            )
        )


        return {

            "case_id": str(
                case_id
            ),

            "sources": [
                {
                    "id": str(
                        source.id
                    ),
                    "name": source.name,
                    "type": (
                        source.source_type.value
                    ),
                }
                for source in sources
            ],

            "statistics": {

                "sources": len(
                    sources
                ),

                "evidence": len(
                    evidence
                ),

                "entities": len(
                    entities
                ),

            },

            "entities": [

                {
                    "id": str(
                        entity.id
                    ),
                    "type": (
                        entity.entity_type.value
                    ),
                    "value": entity.value,
                    "confidence": (
                        entity.confidence
                    ),
                }

                for entity in entities

            ],

            "evidence": [

                {
                    "id": str(
                        item.id
                    ),
                    "type": (
                        item.evidence_type.value
                    ),
                    "value": item.value,
                }

                for item in evidence

            ],

        }