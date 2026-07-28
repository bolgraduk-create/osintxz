"""
Generic repository.

Every repository in the project must inherit from
GenericRepository.

This class provides common CRUD operations while remaining
independent of any specific ORM model.
"""

from __future__ import annotations

from typing import Any
from typing import Generic
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import BaseModel


ModelType = TypeVar("ModelType", bound=BaseModel)


class GenericRepository(Generic[ModelType]):
    """
    Generic SQLAlchemy repository.
    """

    model: type[ModelType]

    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    # =====================================================
    # Query
    # =====================================================

    def query(self) -> Select[tuple[ModelType]]:
        """
        Base query.
        """

        return select(self.model)

    # =====================================================
    # Get
    # =====================================================

    def get(
        self,
        entity_id: UUID,
    ) -> ModelType | None:
        """
        Returns entity by id.
        """

        return self.session.get(
            self.model,
            entity_id,
        )

    def get_or_none(
        self,
        entity_id: UUID,
    ) -> ModelType | None:
        """
        Alias for readability.
        """

        return self.get(entity_id)

    def get_required(
        self,
        entity_id: UUID,
    ) -> ModelType:
        """
        Returns entity or raises LookupError.
        """

        entity = self.get(entity_id)

        if entity is None:
            raise LookupError(
                f"{self.model.__name__} "
                f"{entity_id} not found."
            )

        return entity

    # =====================================================
    # List
    # =====================================================

    def all(self) -> list[ModelType]:
        """
        Returns all records.
        """

        return list(
            self.session.scalars(
                self.query()
            )
        )

    def count(self) -> int:
        """
        Returns number of records.

        NOTE:
        This implementation will be optimized later
        using SQL COUNT().
        """

        return len(self.all())

    # =====================================================
    # Create
    # =====================================================

    def add(
        self,
        entity: ModelType,
    ) -> ModelType:
        """
        Adds entity to session.
        """

        self.session.add(entity)

        return entity

    # =====================================================
    # Delete
    # =====================================================

    def delete(
        self,
        entity: ModelType,
    ) -> None:
        """
        Hard delete.
        """

        self.session.delete(entity)

    # =====================================================
    # Exists
    # =====================================================

    def exists(
        self,
        entity_id: UUID,
    ) -> bool:
        """
        Returns True if entity exists.
        """

        return self.get(entity_id) is not None

    # =====================================================
    # Flush
    # =====================================================

    def flush(self) -> None:
        """
        Flush current session.
        """

        self.session.flush()

    # =====================================================
    # Refresh
    # =====================================================

    def refresh(
        self,
        entity: ModelType,
    ) -> None:
        """
        Refresh entity from database.
        """

        self.session.refresh(entity)

    # =====================================================
    # Merge
    # =====================================================

    def merge(
        self,
        entity: ModelType,
    ) -> ModelType:
        """
        Merge detached entity.
        """

        return self.session.merge(entity)

    # =====================================================
    # Commit
    # =====================================================

    def commit(self) -> None:
        """
        Explicit commit.

        Mostly used outside FastAPI.
        """

        self.session.commit()

    # =====================================================
    # Rollback
    # =====================================================

    def rollback(self) -> None:
        """
        Rollback current transaction.
        """

        self.session.rollback()

    # =====================================================
    # Update helper
    # =====================================================

    def update(
        self,
        entity: ModelType,
        **fields: Any,
    ) -> ModelType:
        """
        Updates entity attributes.
        """

        for key, value in fields.items():

            setattr(
                entity,
                key,
                value,
            )

        return entity