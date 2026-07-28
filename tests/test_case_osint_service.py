"""
Test Case OSINT service.

Checks:

- case OSINT overview generation
- access to stored OSINT data
"""

from app.database.session import get_session
from app.database.init_db import init_database

from app.models.case import Case

from app.services.osint_result_service import (
    OsintResultService,
)

from app.services.case_osint_service import (
    CaseOsintService,
)


def run_test():

    print("=" * 70)
    print("CASE OSINT SERVICE TEST")
    print("=" * 70)


    init_database()


    session_generator = get_session()

    session = next(
        session_generator
    )


    try:

        print("\n[1] Creating test case...")


        case = Case(
            title="Case OSINT Overview Test",
            description="Testing case OSINT aggregation",
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


        print("\n[2] Initializing services...")


        result_service = OsintResultService(
            session
        )


        case_osint_service = CaseOsintService(
            result_service
        )


        print(
            "[ OK ] Services initialized"
        )


        print("\n[3] Building case overview...")


        overview = case_osint_service.get_overview(
            case.id
        )


        print(
            "[ OK ] Overview created"
        )


        print("\nStatistics:")

        print(
            overview["statistics"]
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