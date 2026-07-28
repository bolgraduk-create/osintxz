"""
Entity domain model.

Represents an extracted entity from a Case.

Examples:

- Person
- Organization
- Phone
- Email
- Address
- Username
- Domain
- IP
- Vehicle
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
    from app.models.evidence_entity import EvidenceEntity


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    USERNAME = "username"
    DOMAIN = "domain"
    URL = "url"
    IP = "ip"
    VEHICLE = "vehicle"
    DOCUMENT = "document"
    ACCOUNT = "account"
    OTHER = "other"


class Entity(
    TimestampMixin,
    SoftDeleteMixin,
    DescriptionMixin,
    BaseModel,
):
    """
    Extracted entity.
    """

    __tablename__ = "entities"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[EntityType] = mapped_column(
        SqlEnum(EntityType, name="entity_type"),
        nullable=False,
        index=True,
    )

    value: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
    )

    normalized_value: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="entities",
    )

    evidence_links: Mapped[list["EvidenceEntity"]] = relationship(
        "EvidenceEntity",
        back_populates="entity",
        cascade="all, delete-orphan",
    )


Index(
    "ix_entities_case_type",
    Entity.case_id,
    Entity.entity_type,
)

Index(
    "ix_entities_case_value",
    Entity.case_id,
    Entity.value,
)