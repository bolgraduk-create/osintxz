"""
Project domain model.

A Project groups multiple investigation cases inside a Workspace.
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
    from app.models.case import Case
    from app.models.workspace import Workspace


class Project(
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
    ActiveMixin,
    DescriptionMixin,
):
    """
    Investigation project.

    Every project belongs to exactly one Workspace.

    A project may contain many investigation cases.
    """

    __tablename__ = "projects"

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
    # Foreign Keys
    # ==========================================================

    workspace_id: Mapped = mapped_column(
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="projects",
        lazy="selectin",
    )

    cases: Mapped[list["Case"]] = relationship(
        "Case",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            "Project("
            f"id={self.id}, "
            f"name={self.name!r}"
            ")"
        )