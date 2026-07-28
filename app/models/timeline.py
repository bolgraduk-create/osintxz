"""
Timeline event domain model.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime
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


class TimelineEventType(str, Enum):
    MESSAGE = "message"
    CALL = "call"
    LOGIN = "login"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    PHOTO = "photo"
    VIDEO = "video"
    LOCATION = "location"
    CUSTOM = "custom"


class TimelineEvent(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Timeline event inside an investigation.
    """

    __tablename__ = "timeline_events"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
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

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
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


Index(
    "ix_timeline_case_time",
    TimelineEvent.case_id,
    TimelineEvent.occurred_at,
)

Index(
    "ix_timeline_case_type",
    TimelineEvent.case_id,
    TimelineEvent.event_type,
)