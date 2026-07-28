"""
Search index domain model.

Stores searchable references
to investigation objects.
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
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel
from app.database.mixins import (
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.case import Case


class SearchObjectType(str, Enum):
    """
    Searchable object types.
    """

    MESSAGE = "message"
    DOCUMENT = "document"
    EVIDENCE = "evidence"
    ENTITY = "entity"
    ARTIFACT = "artifact"
    REPORT = "report"
    NOTE = "note"


class SearchIndex(
    TimestampMixin,
    SoftDeleteMixin,
    BaseModel,
):
    """
    Searchable object index.
    """

    __tablename__ = "search_indexes"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    object_type: Mapped[SearchObjectType] = mapped_column(
        SqlEnum(
            SearchObjectType,
            name="search_object_type",
        ),
        nullable=False,
        index=True,
    )

    object_id: Mapped[UUID] = mapped_column(
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
        back_populates="search_indexes",
    )

    def __repr__(self) -> str:
        return (
            f"SearchIndex("
            f"id={self.id}, "
            f"object_type={self.object_type.value!r}"
            f")"
        )


Index(
    "ix_search_indexes_object",
    SearchIndex.object_type,
    SearchIndex.object_id,
)

Index(
    "ix_search_indexes_case_type",
    SearchIndex.case_id,
    SearchIndex.object_type,
)