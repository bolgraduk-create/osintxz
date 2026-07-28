"""
Test OSINT result service.

Checks:

- reading OSINT sources
- reading evidence
- reading entities
- building summary
"""

from app.database.session import get_session
from app.database.init_db import init_database

from app.models.case import Case

from app.services.osint_result_service import (
    OsintResultService,
)


def run_test():

    print("=" * 70)
    print("OSINT RESULT SERVICE TEST")
    print("=" * 70)


    init_database()


    session_generator = get_session()

    session = next(
        session_generator
    )


    try:

        print("\n[1] Creating test case...")


        case = Case(
            title="OSINT Result Service Test",
            description="Testing OSINT result access layer",
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


        print("\n[2] Initializing service...")


        service = OsintResultService(
            session
        )


        print(
            "[ OK ] Service initialized"
        )


        print("\n[3] Reading OSINT data...")


        sources = service.get_case_sources(
            case.id
        )

        evidence = service.get_case_evidence(
            case.id
        )

        entities = service.get_case_entities(
            case.id
        )


        print(
            "[ OK ] Sources:",
            len(sources),
        )

        print(
            "[ OK ] Evidence:",
            len(evidence),
        )

        print(
            "[ OK ] Entities:",
            len(entities),
        )


        print("\n[4] Building summary...")


        summary = service.build_summary(
            case.id
        )


        print(
            summary
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