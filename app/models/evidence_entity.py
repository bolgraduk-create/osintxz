"""
Evidence-Entity association model.

Represents links between evidence
objects and extracted entities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.entity import Entity


class EvidenceEntity(
    BaseModel,
):
    """
    Many-to-many relation between
    Evidence and Entity.
    """

    __tablename__ = "evidence_entities"

    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "evidences.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "entities.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="entity_links",
    )

    entity: Mapped["Entity"] = relationship(
        "Entity",
        back_populates="evidence_links",
    )


Index(
    "ix_evidence_entities_unique",
    EvidenceEntity.evidence_id,
    EvidenceEntity.entity_id,
    unique=True,
)