"""
Case domain model.

A Case represents a single investigation.

Every object in the investigation belongs
to exactly one Case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.ai_analysis import AIAnalysis
    from app.models.artifact import Artifact
    from app.models.document import Document
    from app.models.entity import Entity
    from app.models.evidence import Evidence
    from app.models.message import Message
    from app.models.note import Note
    from app.models.project import Project
    from app.models.relationship import Relationship
    from app.models.report import Report
    from app.models.source import Source
    from app.models.timeline_event import TimelineEvent
    from app.models.search_index import SearchIndex


class Case(
    TimestampMixin,
    SoftDeleteMixin,
    BaseModel,
):
    """
    Investigation case.
    """

    __tablename__ = "cases"

    # ==========================================================
    # Basic information
    # ==========================================================

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ==========================================================
    # Foreign keys
    # ==========================================================

    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    owner_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    project: Mapped["Project | None"] = relationship(
        "Project",
        back_populates="cases",
    )

    sources: Mapped[list["Source"]] = relationship(
        "Source",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    evidences: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    relationships: Mapped[list["Relationship"]] = relationship(
        "Relationship",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        "TimelineEvent",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    ai_analyses: Mapped[list["AIAnalysis"]] = relationship(
        "AIAnalysis",
        back_populates="case",
        cascade="all, delete-orphan",
    )



    search_indexes: Mapped[list["SearchIndex"]] = relationship(
        "SearchIndex",
        back_populates="case",
        cascade="all, delete-orphan",
    )



    def __repr__(self) -> str:
        return (
            f"Case("
            f"id={self.id}, "
            f"title={self.title!r}"
            f")"
        )