"""
Relationship domain model.

Represents a relationship between two entities.
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
    from app.models.entity import Entity


class RelationshipType(str, Enum):
    KNOWS = "knows"
    CONTACTED = "contacted"
    CALLED = "called"
    EMAILED = "emailed"
    MESSAGED = "messaged"
    MEMBER_OF = "member_of"
    OWNS = "owns"
    LOCATED_AT = "located_at"
    RELATED_TO = "related_to"
    OTHER = "other"


class Relationship(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Relationship between two entities.
    """

    __tablename__ = "relationships"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relationship_type: Mapped[RelationshipType] = mapped_column(
        SqlEnum(RelationshipType, name="relationship_type"),
        nullable=False,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="relationships",
    )

    source_entity: Mapped["Entity"] = relationship(
        "Entity",
        foreign_keys=[source_entity_id],
    )

    target_entity: Mapped["Entity"] = relationship(
        "Entity",
        foreign_keys=[target_entity_id],
    )


Index(
    "ix_relationships_case_type",
    Relationship.case_id,
    Relationship.relationship_type,
)

Index(
    "ix_relationships_source_target",
    Relationship.source_entity_id,
    Relationship.target_entity_id,
)