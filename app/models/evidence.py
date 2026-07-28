"""
Evidence model.

Evidence represents any extracted object from a Source.

Examples:

- image
- video
- audio
- document
- archive
- phone number
- email
- url
- location
- contact
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
    from app.models.source import Source
    from app.models.evidence_entity import EvidenceEntity

class EvidenceType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    CONTACT = "contact"
    LOCATION = "location"
    LINK = "link"
    PHONE = "phone"
    EMAIL = "email"
    USERNAME = "username"
    HASH = "hash"
    METADATA = "metadata"
    MESSAGE = "message"
    OTHER = "other"


class Evidence(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Extracted evidence.
    """

    __tablename__ = "evidences"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    evidence_type: Mapped[EvidenceType] = mapped_column(
        SqlEnum(EvidenceType, name="evidence_type"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    value: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )   

    file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="evidences",
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="evidences",
)


    entity_links: Mapped[list["EvidenceEntity"]] = relationship(
        "EvidenceEntity",
        back_populates="evidence",
        cascade="all, delete-orphan",
)


Index(
    "ix_evidences_case_type",
    Evidence.case_id,
    Evidence.evidence_type,
)

Index(
    "ix_evidences_source_type",
    Evidence.source_id,
    Evidence.evidence_type,
)