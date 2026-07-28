"""
AI analysis repository.

Provides database operations
for AI generated analysis results.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_analysis import (
    AIAnalysis,
)

from app.repositories.base_repository import (
    BaseRepository,
)


class AIAnalysisRepository(
    BaseRepository[AIAnalysis],
):
    """
    Repository for AIAnalysis model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            AIAnalysis,
        )


    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[AIAnalysis]:
        """
        Return all AI analyses
        belonging to a case.
        """

        result = self.session.execute(
            select(AIAnalysis)
            .where(
                AIAnalysis.case_id == case_id
            )
            .order_by(
                AIAnalysis.created_at.desc()
            )
        )

        return list(
            result.scalars().all()
        )


    def get_latest(
        self,
        case_id: UUID,
    ) -> AIAnalysis | None:
        """
        Return latest AI analysis
        for a case.
        """

        result = self.session.execute(
            select(AIAnalysis)
            .where(
                AIAnalysis.case_id == case_id
            )
            .order_by(
                AIAnalysis.created_at.desc()
            )
            .limit(1)
        )

        return result.scalar_one_or_none()


    def get_by_model(
        self,
        model_name: str,
    ) -> list[AIAnalysis]:
        """
        Find analyses created
        by specific AI model.
        """

        result = self.session.execute(
            select(AIAnalysis)
            .where(
                AIAnalysis.model_name == model_name
            )
        )

        return list(
            result.scalars().all()
        )


    def delete_by_id(
        self,
        analysis_id: UUID,
    ) -> bool:
        """
        Soft delete AI analysis.
        """

        analysis = self.get(
            analysis_id
        )

        if analysis is None:
            return False

        analysis.soft_delete()

        self.session.flush()

        return True