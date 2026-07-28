"""
Workspace integration test.

Checks:

- case creation
- evidence creation
- entity creation
- relationship creation
- report creation
- workspace aggregation

Does NOT test UI.
"""

from __future__ import annotations


from app.database.init_db import init_database
from app.database.session import create_session


from app.models.evidence import (
    EvidenceType,
)

from app.models.entity import (
    EntityType,
)

from app.models.relationship import (
    RelationshipType,
)


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


from app.application.case_workspace_service import (
    CaseWorkspaceService,
)

from app.models.source import (
    SourceType,
)

from app.services.source_service import (
    SourceService,
)


from app.models.report import (
    ReportType,
)



def run_test():

    print(
        "Starting workspace integration test..."
    )


    init_database()


    session = create_session()


    try:


        # ======================================================
        # Services
        # ======================================================

        case_service = CaseService(
            session
        )


        evidence_service = EvidenceService(
            session
        )

        source_service = SourceService(
            session
        )


        entity_service = EntityService(
            session
        )


        relationship_service = RelationshipService(
            session
        )


        report_service = ReportService(
            session
        )


        workspace_service = CaseWorkspaceService(

            case_service=case_service,

            evidence_service=evidence_service,

            entity_service=entity_service,

            relationship_service=relationship_service,

            report_service=report_service,

        )



        # ======================================================
        # Create case
        # ======================================================

        case = case_service.create_case(

            title="Workspace Test Case",

            description="Integration test",

        )


        session.commit()


        print(
            "Case created:",
            case.id
        )




        source = source_service.create_source(
            case_id=case.id,
            name="Test Source",
            source_type=SourceType.FILE,
            path="test.jpg",
        )

        session.commit()

        print(
            "Source created:",
            source.id,
        )



        # ======================================================
        # Evidence
        # ======================================================

        evidence = evidence_service.create_evidence(

            case_id=case.id,

           source_id=source.id,

            evidence_type=EvidenceType.IMAGE,

            title="Test image",

            value="test.jpg",

        )


        session.commit()


        print(
            "Evidence created:",
            evidence.id
        )



        # ======================================================
        # Entity
        # ======================================================

        entity = entity_service.create_entity(

            case_id=case.id,

            entity_type=EntityType.PERSON,

            value="John Smith",

        )


        session.commit()


        print(
            "Entity created:",
            entity.id
        )



        # ======================================================
        # Relationship
        # ======================================================

        relationship = relationship_service.create_relationship(

            case_id=case.id,

            source_entity_id=entity.id,

            target_entity_id=entity.id,

            relationship_type=RelationshipType.RELATED_TO,

            description="Self relation test",

        )


        session.commit()


        print(
            "Relationship created:",
            relationship.id
        )



        # ======================================================
        # Report
        # ======================================================

        report = report_service.create_report(

            case_id=case.id,

            title="Initial Report",

            content="Test report content",

            report_type=ReportType.AI_ANALYSIS,

        )


        session.commit()


        print(
            "Report created:",
            report.id
        )



        # ======================================================
        # Workspace
        # ======================================================

        workspace = workspace_service.get_workspace(

            str(case.id)

        )


        print()

        print(
            "WORKSPACE RESULT"
        )


        print(
            workspace["statistics"]
        )



        assert (
            workspace["statistics"]["evidence"]
            == 1
        )


        assert (
            workspace["statistics"]["entities"]
            == 1
        )


        assert (
            workspace["statistics"]["reports"]
            == 1
        )



        print()

        print(
            "WORKSPACE TEST PASSED"
        )



    finally:

        session.close()



if __name__ == "__main__":

    run_test()