"""
Base repository.

Provides common CRUD operations
for all repositories.
"""

from __future__ import annotations

from typing import Generic
from typing import Type
from typing import TypeVar
from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import BaseModel


ModelType = TypeVar(
    "ModelType",
    bound=BaseModel,
)


class BaseRepository(
    Generic[ModelType],
):
    """
    Generic repository.

    All repositories inherit from this class.
    """

    def __init__(
        self,
        session: Session,
        model: Type[ModelType],
    ):
        self.session = session
        self.model = model

    def get(
        self,
        object_id: UUID,
    ) -> ModelType | None:
        """
        Get object by primary key.
        """

        return self.session.get(
            self.model,
            object_id,
        )

    def get_all(
        self,
    ) -> list[ModelType]:
        """
        Return all objects.
        """

        result = self.session.execute(
            select(self.model)
        )

        return list(
            result.scalars().all()
        )

    def create(
        self,
        obj: ModelType | None = None,
        **kwargs,
    ) -> ModelType:
        """
        Create object.

        Supports:

        create(Model(...))

        and:

        create(
            field=value
        )
        """

        if obj is None:

            obj = self.model(
                **kwargs
            )

        self.session.add(
            obj
        )

        self.session.flush()

        return obj

    def refresh(
        self,
        obj: ModelType,
    ) -> ModelType:
        """
        Refresh object from database.
        """

        self.session.refresh(obj)

        return obj

    def delete(
        self,
        obj: ModelType,
    ) -> None:
        """
        Permanently delete object.
        """

        self.session.delete(obj)
        self.session.flush()

    def exists(
        self,
        object_id: UUID,
    ) -> bool:
        """
        Check whether object exists.
        """

        return self.get(object_id) is not None

    def count(
        self,
    ) -> int:
        """
        Return number of records.
        """

        result = self.session.execute(
            select(func.count()).select_from(self.model)
        )

        return int(
            result.scalar_one()
        )