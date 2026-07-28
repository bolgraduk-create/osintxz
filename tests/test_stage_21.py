"""
Stage 21 test.

Tests InvestigationService.
"""


from app.database.session import create_session

from app.services.investigation_service import (
    InvestigationService,
)



def run_test():

    print(
        "\n=== Stage 21 test started ===\n"
    )


    session = create_session()


    try:

        service = InvestigationService(
            session
        )


        print(
            "[1] Creating investigation..."
        )


        case = service.create_investigation(
            title="Stage 21 Investigation",
            description="Service integration test",
        )


        print(
            "Created:",
            case.id,
            case.title,
        )


        print(
            "\n[2] Loading investigation..."
        )


        loaded = service.get_investigation(
            case.id
        )


        assert loaded is not None

        print(
            "Loaded:",
            loaded.title,
        )


        print(
            "\n[3] Loading context..."
        )


        context = service.get_context(
            case.id
        )


        assert "case" in context
        assert "evidence" in context
        assert "entities" in context
        assert "relationships" in context
        assert "reports" in context


        print(
            "Context keys:",
            list(context.keys())
        )


        print(
            "\n[4] Deleting investigation..."
        )


        result = service.delete_investigation(
            case.id
        )


        assert result is True


        print(
            "Deleted:",
            result
        )


        print(
            "\n=== Stage 21 test PASSED ==="
        )


    finally:

        session.close()



if __name__ == "__main__":

    run_test()