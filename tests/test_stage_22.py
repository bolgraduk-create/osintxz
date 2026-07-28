"""
Stage 22 integration test.

Tests AI investigation workflow:

Case
 ↓
InvestigationService
 ↓
AI Manager
 ↓
Mock AI Provider
 ↓
AI Analysis Repository
"""


from __future__ import annotations


from app.database.init_db import init_database
from app.database.session import create_session


from app.services.investigation_service import (
    InvestigationService,
)

from app.services.ai_investigation_service import (
    AIInvestigationService,
)

from app.repositories.ai_analysis_repository import (
    AIAnalysisRepository,
)


from app.ai.ai_manager import AIManager



class MockProvider:
    """
    Mock AI provider.

    Replaces Ollama/OpenAI
    during tests.
    """


    def __init__(
        self,
    ):

        self.connected = False

        self.model_name = (
            "mock-model"
        )



    def initialize(
        self,
    ):

        self.connected = False



    def connect(
        self,
    ) -> bool:

        self.connected = True

        return True



    def close(
        self,
    ):

        self.connected = False



    def generate(
        self,
        prompt: str,
        **kwargs,
    ) -> str:

        return """
Mock AI analysis result.

Entities:

- Person A
- Organization B


Relationships:

- Person A works with Organization B


Conclusion:

Investigation analyzed successfully.
"""



    def get_model_info(
        self,
    ) -> dict:

        return {

            "provider":
                "mock",

            "model":
                self.model_name,

            "connected":
                self.connected,

        }



    def metadata(
        self,
    ) -> dict:

        return {

            "type":
                "mock",

            "model":
                self.model_name,

            "status":
                (
                    "ready"
                    if self.connected
                    else "offline"
                ),

        }



    def health_check(
        self,
    ) -> bool:

        return self.connected





def run_test():

    print(
        "\n=== Stage 22 test started ===\n"
    )


    init_database()


    session = create_session()



    try:


        # =====================================================
        # 1. Create investigation
        # =====================================================

        print(
            "[1] Creating investigation..."
        )


        investigation_service = InvestigationService(
            session
        )


        case = (
            investigation_service
            .create_investigation(
                title=
                    "AI Test Investigation",

                description=
                    "AI workflow test",
            )
        )


        print(
            "Created:",
            case.id
        )



        # =====================================================
        # 2. Initialize AI
        # =====================================================

        print(
            "\n[2] Initializing AI..."
        )


        ai_manager = AIManager(
            provider_name="mock",
        )


        ai_manager.initialize()

        ai_manager.connect()



        print(
            "AI:",
            ai_manager.info()
        )



        # =====================================================
        # 3. Run AI analysis
        # =====================================================

        print(
            "\n[3] Running AI analysis..."
        )


        ai_service = AIInvestigationService(
            session=session,
            ai_manager=ai_manager,
        )


        result = (
            ai_service
            .analyze(
                case.id
            )
        )


        print(
            "Analysis result:"
        )


        print(
            result
        )



        # =====================================================
        # 4. Verify database
        # =====================================================

        print(
            "\n[4] Checking saved AI analysis..."
        )


        repository = AIAnalysisRepository(
            session
        )


        analyses = (
            repository
            .get_by_case(
                case.id
            )
        )


        print(
            "Saved analyses:",
            len(analyses)
        )



        assert len(analyses) > 0



        latest = analyses[0]


        print(
            "Latest model:",
            latest.model_name
        )


        print(
            "Content:"
        )


        print(
            latest.content
        )



        print(
            "\n=== Stage 22 test PASSED ==="
        )



    finally:

        session.close()



if __name__ == "__main__":

    run_test()