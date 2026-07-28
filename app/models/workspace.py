"""
Workspace domain model.

A Workspace is the top-level container for investigation projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    from app.models.workspace_membership import WorkspaceMembership


class Workspace(
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
    ActiveMixin,
    DescriptionMixin,
):
    """
    Collaborative workspace.

    A workspace contains one or more investigation projects.
    Access is managed through WorkspaceMembership.
    """

    __tablename__ = "workspaces"

    # ==========================================================
    # Basic information
    # ==========================================================

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        "WorkspaceMembership",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Workspace("
            f"id={self.id}, "
            f"name={self.name!r}"
            f")"
        )