"""
Test OSINT investigation service.

Checks:

- database initialization
- case creation
- OSINT manager
- connector pipeline
- result storage
"""

from app.database.session import get_session
from app.database.init_db import init_database

from app.models.case import Case

from app.osint.manager import OsintManager
from app.osint.pipeline import OsintPipeline

from app.osint.models import (
    OsintTarget,
    OsintTargetType,
    ConnectorRequest,
)

from app.services.osint_investigation_service import (
    OsintInvestigationService,
)


def run_test():

    print("=" * 70)
    print("OSINT INVESTIGATION SERVICE TEST")
    print("=" * 70)


    init_database()


    session_generator = get_session()

    session = next(
        session_generator
    )


    try:

        print("\n[1] Creating test case...")


        case = Case(
            title="OSINT Connector Integration Test",
            description="Testing OSINT pipeline integration",
        )


        session.add(
            case
        )

        session.commit()

        session.refresh(
            case
        )


        print(
            "[ OK ] Case created:",
            case.id,
        )


        print("\n[2] Initializing OSINT manager...")


        manager = OsintManager()


        pipeline = OsintPipeline(
            manager
        )


        print(
            "[ OK ] Connectors loaded:",
            len(manager.registry),
        )


        print("\n[3] Creating investigation service...")


        service = OsintInvestigationService(
            session=session,
            pipeline=pipeline,
        )


        print(
            "[ OK ] Service initialized"
        )


        print("\n[4] Running OSINT investigation...")


        target = OsintTarget(
            target_type=OsintTargetType.DOMAIN,
            value="example.com",
            case_id=str(case.id),
        )


        request = ConnectorRequest(
            target=target,
            timeout=30,
            save_raw_output=False,
        )


        result = service.run_investigation(
            case_id=case.id,
            request=request,
        )


        session.commit()


        print(
            "[ OK ] Investigation completed"
        )


        print("\nResult:")


        print(
            "Source ID:",
            result["source_id"],
        )

        print(
            "Connectors executed:",
            result["connectors_executed"],
        )

        print(
            "Evidence created:",
            result["evidence_created"],
        )

        print(
            "Entities created:",
            result["entities_created"],
        )


        print("\n" + "=" * 70)

        print(
            "TEST PASSED"
        )

        print("=" * 70)



    finally:

        session.close()



if __name__ == "__main__":

    run_test()