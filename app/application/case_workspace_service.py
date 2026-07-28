"""
Case workspace application service.

Responsible for:

- preparing investigation workspace data
- aggregating case information
- providing UI-ready workspace state

Does NOT:

- access database directly
- contain UI logic
- perform analysis
"""

from __future__ import annotations


from typing import Any

from uuid import UUID


from app.services.case_service import (
    CaseService,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.report_service import (
    ReportService,
)



class CaseWorkspaceService:
    """
    Application service for case workspace.
    """



    def __init__(
        self,
        case_service: CaseService | None = None,
        evidence_service: EvidenceService | None = None,
        entity_service: EntityService | None = None,
        relationship_service: RelationshipService | None = None,
        report_service: ReportService | None = None,
    ):

        self.case_service = case_service

        self.evidence_service = evidence_service

        self.entity_service = entity_service

        self.relationship_service = relationship_service

        self.report_service = report_service



    # ==========================================================
    # Workspace
    # ==========================================================

    def get_workspace(
        self,
        case_id: str,
    ) -> dict[str, Any] | None:
        """
        Build workspace data.
        """


        if self.case_service is None:

            return None



        case_uuid = UUID(
            case_id
        )



        case = (
            self.case_service.get_case(
                case_uuid
            )
        )


        if case is None:

            return None



        evidence_list = []

        if self.evidence_service:

            evidence_list = (
                self.evidence_service
                .get_case_evidence(
                    case_uuid
                )
            )



        entity_list = []

        if self.entity_service:

            entity_list = (
                self.entity_service
                .get_case_entities(
                    case_uuid
                )
            )



        relationship_list = []

        if self.relationship_service:

            relationship_list = (
                self.relationship_service
                .get_case_relationships(
                    case_uuid
                )
            )



        report_list = []

        if self.report_service:

            report_list = (
                self.report_service
                .get_case_reports(
                    case_uuid
                )
            )



        return {

            "case": {

                "id":
                    str(case.id),

                "title":
                    case.title,

                "description":
                    case.description,

            },


            "statistics": {

                "evidence":
                    len(evidence_list),

                "entities":
                    len(entity_list),

                "relationships":
                    len(relationship_list),

                "reports":
                    len(report_list),

                "timeline":
                    0,

            },



            "evidence": [

                {

                    "id":
                        str(item.id),

                    "title":
                        item.title,

                    "type":
                        item.evidence_type.value,

                    "value":
                        item.value,

                }

                for item in evidence_list

            ],



            "entities": [

                {

                    "id":
                        str(item.id),

                    "type":
                        item.entity_type.value,

                    "value":
                        item.value,

                    "confidence":
                        item.confidence,

                }

                for item in entity_list

            ],



            "relationships": [

                {

                    "id":
                        str(item.id),

                    "type":
                        item.relationship_type.value,

                    "source":
                        str(item.source_entity_id),

                    "target":
                        str(item.target_entity_id),

                    "confidence":
                        item.confidence,

                }

                for item in relationship_list

            ],



            "reports": [

                {

                    "id":
                        str(item.id),

                    "title":
                        item.title,

                    "content":
                        item.content,

                    "type":
                        item.report_type,

                }

                for item in report_list

            ],



            "timeline": [],

        }