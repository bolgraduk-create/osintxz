"""
AI analysis service.

Contains business logic related
to AI-generated analysis results.

AI processing itself is handled
by analysis modules.

This service only manages
AI analysis records.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import AIAnalysis

from app.repositories.ai_analysis_repository import (
    AIAnalysisRepository,
)


class AIAnalysisService:
    """
    Service for managing AI analyses.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = AIAnalysisRepository(
            session
        )


    def create_analysis(
        self,
        case_id: UUID,
        analysis_type: str,
        result: str,
        model_name: str | None = None,
        confidence: float | None = None,
    ) -> AIAnalysis:
        """
        Store AI analysis result.
        """

        analysis = AIAnalysis(
            case_id=case_id,
            analysis_type=analysis_type,
            model_name=model_name,
            result=result,
            confidence=confidence,
        )

        return self.repository.create(
            analysis
        )


    def get_analysis(
        self,
        analysis_id: UUID,
    ) -> AIAnalysis | None:
        """
        Get AI analysis by id.
        """

        return self.repository.get(
            analysis_id
        )


    def get_case_analyses(
        self,
        case_id: UUID,
    ) -> list[AIAnalysis]:
        """
        Return all AI analyses
        for a case.
        """

        return self.repository.get_by_case(
            case_id
        )


    def get_by_type(
        self,
        analysis_type: str,
    ) -> list[AIAnalysis]:
        """
        Return analyses by type.
        """

        return self.repository.get_by_type(
            analysis_type
        )


    def delete_analysis(
        self,
        analysis_id: UUID,
    ) -> bool:
        """
        Soft delete AI analysis.
        """

        analysis = self.repository.get(
            analysis_id
        )

        if analysis is None:
            return False

        analysis.soft_delete()

        self.repository.session.flush()

        return True