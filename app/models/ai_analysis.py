"""
AI Analysis domain model.

Stores results produced by AI modules.

An AI analysis belongs to exactly one Case
and describes the result of an automated analysis process.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel

from app.database.mixins import (
    DescriptionMixin,
    SoftDeleteMixin,
    TimestampMixin,
)


if TYPE_CHECKING:
    from app.models.case import Case


class AnalysisType(str, Enum):
    """
    Supported AI analysis types.
    """

    SENTIMENT = "sentiment"

    RELATIONSHIP = "relationship"

    ENTITY_EXTRACTION = "entity_extraction"

    SUMMARIZATION = "summarization"

    CLASSIFICATION = "classification"

    OTHER = "other"


class AIAnalysis(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    AI-generated analysis result.
    """

    __tablename__ = "ai_analyses"


    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


    analysis_type: Mapped[AnalysisType] = mapped_column(
        SqlEnum(
            AnalysisType,
            name="analysis_type",
        ),
        nullable=False,
        index=True,
    )


    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


    result: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    @property
    def content(self) -> str:
        """
        Backward compatibility alias.

        Some services/tests use content naming.
        Database field remains result.
        """

        return self.result


    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )


    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="ai_analyses",
    )


Index(
    "ix_ai_analysis_case_type",
    AIAnalysis.case_id,
    AIAnalysis.analysis_type,
)