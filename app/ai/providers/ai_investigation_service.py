"""
AI Investigation Service.

Runs AI analysis workflows
for investigations.

Responsibilities:

- prepare investigation context
- select analysis type
- execute AI request
- store AI result

Does NOT:

- collect OSINT data
- build graphs
- create reports
"""

from __future__ import annotations


from typing import Any
from uuid import UUID


from sqlalchemy.orm import Session


from app.ai.ai_manager import AIManager

from app.ai.prompts import (
    IntelligencePrompts,
)

from app.services.investigation_service import (
    InvestigationService,
)

from app.repositories.ai_analysis_repository import (
    AIAnalysisRepository,
)



class AIInvestigationService:
    """
    AI workflow service.
    """


    def __init__(
        self,
        session: Session,
        ai_manager: AIManager,
    ):
        """
        Initialize service.
        """


        self.session = session

        self.ai_manager = ai_manager


        self.investigation_service = (
            InvestigationService(
                session
            )
        )


        self.repository = (
            AIAnalysisRepository(
                session
            )
        )



    def analyze(
        self,
        case_id: UUID,
    ):
        """
        Run general investigation analysis.
        """


        context = (
            self.investigation_service
            .get_context(
                case_id
            )
        )


        if not context:

            raise ValueError(
                "Investigation not found"
            )


        prompt = (
            IntelligencePrompts
            .investigation_analysis(
                context
            )
        )


        response = (
            self.ai_manager
            .generate(
                prompt
            )
        )


        analysis = (
            self.repository.create(
                case_id=case_id,
                analysis_type="investigation",
                content=response,
                metadata_json={
                    "ai":
                        self.ai_manager.info()
                },
            )
        )


        self.session.commit()


        return analysis



    def analyze_relationships(
        self,
        case_id: UUID,
    ):
        """
        Analyze entity relationships.
        """


        context = (
            self.investigation_service
            .get_context(
                case_id
            )
        )


        prompt = (
            IntelligencePrompts
            .relationship_analysis(
                context.get("entities"),
                context.get("relationships"),
            )
        )


        response = (
            self.ai_manager
            .generate(
                prompt
            )
        )


        analysis = (
            self.repository.create(
                case_id=case_id,
                analysis_type="relationships",
                content=response,
                metadata_json={
                    "ai":
                        self.ai_manager.info()
                },
            )
        )


        self.session.commit()


        return analysis