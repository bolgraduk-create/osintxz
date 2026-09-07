"""
Face profile model.

Represents one user-managed face profile
inside the local Face Memory.

A face profile may contain multiple
confirmed face embeddings collected from
different evidence items and investigations.

The model does NOT automatically assert
real-world identity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    from app.models.face_embedding import (
        FaceEmbedding,
    )


class FaceProfile(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Persistent user-managed face profile.
    """

    __tablename__ = "face_profiles"

    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="active",
        index=True,
    )

    embeddings: Mapped[
        list["FaceEmbedding"]
    ] = relationship(
        "FaceEmbedding",
        back_populates="profile",
        cascade="all, delete-orphan",
    )