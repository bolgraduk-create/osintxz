"""
Report domain model.

Represents a generated report
inside a Case.

Examples:

- Investigation summary
- AI report
- Timeline report
- Relationship report
- Exported analysis
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


class ReportType(str, Enum):
    """
    Supported report types.
    """

    SUMMARY = "summary"
    AI_ANALYSIS = "ai_analysis"
    TIMELINE = "timeline"
    RELATIONSHIP = "relationship"
    EXPORT = "export"
    OTHER = "other"


class Report(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Investigation report.
    """

    __tablename__ = "reports"


    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


    report_type: Mapped[ReportType] = mapped_column(
        SqlEnum(
            ReportType,
            name="report_type",
        ),
        nullable=False,
        index=True,
    )


    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="reports",
    )


Index(
    "ix_reports_case_type",
    Report.case_id,
    Report.report_type,
)