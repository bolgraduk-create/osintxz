"""
Investigation note model.

Represents analyst notes attached to a case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
)

if TYPE_CHECKING:
    from app.models.case import Case


class Note(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Analyst note inside a case.
    """

    __tablename__ = "notes"

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

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="notes",
    )

    def __repr__(self) -> str:
        return (
            f"Note("
            f"id={self.id}, "
            f"title={self.title!r}"
            f")"
        )