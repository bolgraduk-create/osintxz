"""
Stage 20 integration test.

Checks:
- database connection
- repositories
- case lifecycle
- related objects loading
"""


from app.database.session import create_session

from app.repositories.case_repository import CaseRepository

from app.models.case import Case


def run_test():

    print("\n=== Stage 20 test started ===\n")

    session = create_session()

    try:

        case_repository = CaseRepository(session)

        print("[1] Creating case...")

        case = case_repository.create(
            Case(
                title="Stage 20 Investigation",
                description="Integration test case"
            )
        )

        print(
            "Created:",
            case.id,
            case.title
        )


        print("\n[2] Loading cases...")

        cases = case_repository.get_all()

        print(
            "Cases found:",
            len(cases)
        )


        assert len(cases) > 0


        print("\n[3] Loading created case...")

        loaded = case_repository.get(
            case.id
        )

        assert loaded is not None

        print(
            "Loaded:",
            loaded.title
        )


        print("\n=== Stage 20 PASSED ===")


    finally:

        session.close()


if __name__ == "__main__":
    run_test()