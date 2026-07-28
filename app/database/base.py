"""
Base SQLAlchemy models.

Every ORM model in the project must inherit from BaseModel.

The base model provides:

- UUID primary key
- automatic table naming
- common object representation

Infrastructure concerns such as timestamps,
soft deletion and ownership are implemented
through mixins.
"""

from __future__ import annotations

from uuid import UUID
from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import declared_attr
from sqlalchemy.orm import mapped_column


# ==========================================================
# Naming convention
#
# Never change after the first migration.
# ==========================================================

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


metadata = MetaData(
    naming_convention=NAMING_CONVENTION,
)


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base.
    """

    metadata = metadata


class BaseModel(Base):
    """
    Base class for every ORM entity.

    Contains only functionality that every
    database entity must have.
    """

    __abstract__ = True

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """
        Automatic table name.

        Example:

            User -> users

            Project -> projects

            Case -> cases
        """

        return f"{cls.__name__.lower()}s"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(id={self.id})"
        )