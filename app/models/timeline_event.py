"""
Timeline event model.

Represents an event that happened
during an investigation.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    DescriptionMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.entity import Entity


class TimelineEventType(str, Enum):
    """
    Types of investigation events.
    """

    MESSAGE = "message"

    DOCUMENT = "document"

    FILE = "file"

    CALL = "call"

    EMAIL = "email"

    RELATIONSHIP = "relationship"

    ENTITY_CREATED = "entity_created"

    ENTITY_UPDATED = "entity_updated"

    LOCATION = "location"

    OTHER = "other"


class TimelineEvent(
    TimestampMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Event in investigation timeline.
    """

    __tablename__ = "timeline_events"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "entities.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    event_type: Mapped[TimelineEventType] = mapped_column(
        SqlEnum(
            TimelineEventType,
            name="timeline_event_type",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    event_time: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="timeline_events",
    )

    entity: Mapped["Entity | None"] = relationship(
        "Entity",
    )