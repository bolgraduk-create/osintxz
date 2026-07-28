"""
Document domain model.

Represents a document stored inside a Case.

Examples:

- PDF report
- Text file
- Word document
- HTML page
- Exported report
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


class DocumentType(str, Enum):
    """
    Supported document types.
    """

    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    REPORT = "report"
    OTHER = "other"


class Document(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Document stored in a Case.
    """

    __tablename__ = "documents"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "sources.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    document_type: Mapped[DocumentType] = mapped_column(
        SqlEnum(
            DocumentType,
            name="document_type",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    content: Mapped[str | None] = mapped_column(
        Text,
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

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="documents",
    )

    source: Mapped["Source | None"] = relationship(
        "Source",
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return (
            f"Document("
            f"id={self.id}, "
            f"title={self.title!r}"
            f")"
        )


# Composite index
Index(
    "ix_documents_case_type",
    Document.case_id,
    Document.document_type,
)