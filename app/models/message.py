"""
Message model.

Represents a single message imported from any supported source.

Examples:

- Telegram message
- WhatsApp message
- Discord message
- Email
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import Evidence
    from app.models.source import Source


class Message(
    TimestampMixin,
    SoftDeleteMixin,
    BaseModel,
):
    """
    Imported message.
    """

    __tablename__ = "messages"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "sources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "evidences.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    sender: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    receiver: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    chat_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reply_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "messages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="messages",
    )

    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="messages",
    )

    evidence: Mapped["Evidence | None"] = relationship(
        "Evidence",
    )

    reply_to: Mapped["Message | None"] = relationship(
        "Message",
        remote_side="Message.id",
        back_populates="replies",
    )

    replies: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="reply_to",
        cascade="all",
    )

    def __repr__(self) -> str:
        return (
            f"Message("
            f"id={self.id}, "
            f"sender={self.sender!r}"
            f")"
        )


Index(
    "ix_messages_case_sent_at",
    Message.case_id,
    Message.sent_at,
)

Index(
    "ix_messages_source_sent_at",
    Message.source_id,
    Message.sent_at,
)

Index(
    "ix_messages_sender_chat",
    Message.sender,
    Message.chat_name,
)