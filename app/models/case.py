"""
Case domain model.

A Case represents a single investigation.

Every evidence, entity, message, report and AI analysis
belongs to exactly one Case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    ActiveMixin,
    DescriptionMixin,
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.source import Source
    from app.models.evidence import Evidence
    from app.models.message import Message
    from app.models.entity import Entity
    from app.models.relationship import Relationship
    from app.models.timeline import TimelineEvent
    from app.models.artifact import Artifact
    from app.models.ai_analysis import AIAnalysis
    from app.models.report import Report
    from app.models.note import Note
    from app.models.tag import Tag
    from app.models.search_index import SearchIndex
    from app.models.audit_log import AuditLog


class Case(
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
    ActiveMixin,
    DescriptionMixin,
):
    """
    Investigation case.

    This is the central domain object of the platform.
    """

    __tablename__ = "cases"

    # ==========================================================
    # Basic information
    # ==========================================================

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Foreign keys
    # ==========================================================

    project_id: Mapped = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="cases",
        lazy="selectin",
    )

    sources: Mapped[list["Source"]] = relationship(
        "Source",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    relationships: Mapped[list["Relationship"]] = relationship(
        "Relationship",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        "TimelineEvent",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    ai_analyses: Mapped[list["AIAnalysis"]] = relationship(
        "AIAnalysis",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    search_indexes: Mapped[list["SearchIndex"]] = relationship(
        "SearchIndex",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            "Case("
            f"id={self.id}, "
            f"name={self.name!r}"
            ")"
        )