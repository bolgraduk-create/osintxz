"""
Workspace membership domain model.

Represents membership of an Account in a Workspace.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.workspace import Workspace


class WorkspaceRole(str, Enum):
    """
    Workspace member role.
    """

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class WorkspaceMembership(
    BaseModel,
    TimestampMixin,
):
    """
    Associates an Account with a Workspace.
    """

    __tablename__ = "workspace_memberships"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_workspace_membership",
        ),
    )

    # ==========================================================
    # Foreign Keys
    # ==========================================================

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Role
    # ==========================================================

    role: Mapped[WorkspaceRole] = mapped_column(
        SqlEnum(
            WorkspaceRole,
            name="workspace_role",
        ),
        nullable=False,
        default=WorkspaceRole.ANALYST,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="memberships",
        lazy="selectin",
    )

    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="workspace_memberships",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            "WorkspaceMembership("
            f"workspace_id={self.workspace_id}, "
            f"account_id={self.account_id}, "
            f"role={self.role.value}"
            ")"
        )