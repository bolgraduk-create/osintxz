"""
Entity merge model.

Stores entity merge history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.entity import Entity


class EntityMerge(BaseModel):
    """
    Represents merge operation
    between two entities.
    """

    __tablename__ = "entity_merges"

    source_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "entities.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    target_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "entities.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    "ix_entity_merge_source_target",
    EntityMerge.source_entity_id,
    EntityMerge.target_entity_id,
)