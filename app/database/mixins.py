"""
Reusable SQLAlchemy ORM mixins.

Each mixin is responsible for exactly one concern.

Mixins may be combined freely in ORM models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class TimestampMixin:
    """
    Adds creation and modification timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Enables soft deletion.

    Record is considered deleted when deleted_at is not NULL.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        """
        Returns True if the object has been soft deleted.
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """
        Marks object as deleted.
        """
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """
        Restores a previously deleted object.
        """
        self.deleted_at = None


class OwnershipMixin:
    """
    Adds ownership information.

    The referenced User model will be implemented later.
    """

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class DescriptionMixin:
    """
    Adds optional description field.
    """

    description: Mapped[str | None] = mapped_column(
        nullable=True,
    )


class NameMixin:
    """
    Adds required name field.
    """

    name: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )


class ActiveMixin:
    """
    Adds active/inactive flag.
    """

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )