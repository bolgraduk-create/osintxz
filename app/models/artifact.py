"""
Artifact domain model.

Represents any generated artifact inside an investigation.

Examples:
- Graph
- Timeline
- Map
- AI generated image
- Export
- Archive
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


class ArtifactType(str, Enum):
    GRAPH = "graph"
    TIMELINE = "timeline"
    MAP = "map"
    REPORT = "report"
    IMAGE = "image"
    VIDEO = "video"
    EXPORT = "export"
    ARCHIVE = "archive"
    OTHER = "other"


class Artifact(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Generated investigation artifact.
    """

    __tablename__ = "artifacts"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_type: Mapped[ArtifactType] = mapped_column(
        SqlEnum(ArtifactType, name="artifact_type"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="artifacts",
    )


Index(
    "ix_artifacts_case_type",
    Artifact.case_id,
    Artifact.artifact_type,
)