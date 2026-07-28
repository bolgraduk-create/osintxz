"""
Account domain model.

Represents a registered platform account.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import TimestampMixin
from app.database.mixins import SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.workspace_membership import WorkspaceMembership


class Account(
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
):
    """
    Registered platform account.

    Account owns nothing directly.

    Access to Workspaces is granted through WorkspaceMembership.
    """

    __tablename__ = "accounts"

    # ==========================================================
    # Authentication
    # ==========================================================

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ==========================================================
    # Profile
    # ==========================================================

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    # ==========================================================
    # State
    # ==========================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    workspace_memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        "WorkspaceMembership",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Account("
            f"id={self.id}, "
            f"username={self.username!r}"
            f")"
        )