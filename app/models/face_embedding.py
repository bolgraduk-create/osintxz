"""
Face embedding model.

Stores one numerical face descriptor
generated from one detected face.

Architecture:

FaceProfile
    ↓
FaceEmbedding
    ↓
Evidence / Case
    ↓
SFace VECTOR(128)

The embedding represents visual face features.
It does not by itself establish identity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector

from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
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

    from app.models.case import (
        Case,
    )

    from app.models.evidence import (
        Evidence,
    )

    from app.models.face_profile import (
        FaceProfile,
    )


class FaceEmbedding(
    TimestampMixin,
    SoftDeleteMixin,
    BaseModel,
):
    """
    One persistent face observation.
    """

    __tablename__ = "face_embeddings"

    profile_id: Mapped[
        UUID | None
    ] = mapped_column(
        ForeignKey(
            "face_profiles.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    evidence_id: Mapped[
        UUID
    ] = mapped_column(
        ForeignKey(
            "evidences.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    case_id: Mapped[
        UUID
    ] = mapped_column(
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    face_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    face_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(128),
        nullable=False,
    )

    recognizer: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="sface",
    )

    detector: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="yunet",
    )

    detection_confidence: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    bbox_json: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    source_metadata_json: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    profile: Mapped[
        "FaceProfile | None"
    ] = relationship(
        "FaceProfile",
        back_populates="embeddings",
    )

    evidence: Mapped[
        "Evidence"
    ] = relationship(
        "Evidence",
    )

    case: Mapped[
        "Case"
    ] = relationship(
        "Case",
    )


Index(
    "ix_face_embeddings_profile_case",
    FaceEmbedding.profile_id,
    FaceEmbedding.case_id,
)

Index(
    "ix_face_embeddings_evidence_face",
    FaceEmbedding.evidence_id,
    FaceEmbedding.face_id,
    unique=True,
)