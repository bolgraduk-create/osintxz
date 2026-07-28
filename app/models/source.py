"""
Source model.

A Source represents an imported source of information.

Examples:

- Telegram export
- WhatsApp export
- Discord export
- VK export
- Email archive
- PDF
- Image
- Video
- Audio
- Web page
- API
- OSINT tool
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
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
    from app.models.document import Document
    from app.models.evidence import Evidence
    from app.models.message import Message


class SourceType(str, Enum):
    """
    Supported source types.
    """

    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    SIGNAL = "signal"
    DISCORD = "discord"
    VK = "vk"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    X = "x"

    EMAIL = "email"

    FILE = "file"
    DIRECTORY = "directory"

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

    DOCUMENT = "document"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    HTML = "html"

    WEBSITE = "website"

    DATABASE = "database"

    API = "api"

    OSINT = "osint"

    OTHER = "other"


class SourceStatus(str, Enum):
    """
    Source processing status.
    """

    PENDING = "pending"

    PROCESSING = "processing"

    COMPLETED = "completed"

    FAILED = "failed"


class Source(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Imported data source.
    """

    __tablename__ = "sources"


    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(
            SourceType,
            name="source_type",
        ),
        nullable=False,
        index=True,
    )


    status: Mapped[SourceStatus] = mapped_column(
        SqlEnum(
            SourceStatus,
            name="source_status",
        ),
        nullable=False,
        default=SourceStatus.PENDING,
        index=True,
    )


    original_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )


    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )


    size_bytes: Mapped[int | None] = mapped_column(
        nullable=True,
    )


    imported_records: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )


    metadata_json: Mapped[str | None] = mapped_column(
        nullable=True,
    )


    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="sources",
    )


    evidences: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


    def __repr__(
        self,
    ) -> str:

        return (
            f"Source("
            f"id={self.id}, "
            f"name={self.name!r}, "
            f"type={self.source_type.value!r}"
            f")"
        )


Index(
    "ix_sources_case_type",
    Source.case_id,
    Source.source_type,
)