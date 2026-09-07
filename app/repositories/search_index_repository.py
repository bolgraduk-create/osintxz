"""
Search index repository.

Database operations
for searchable objects.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search_index import (
    SearchIndex,
    SearchObjectType,
)

from app.repositories.base_repository import (
    BaseRepository,
)

from sqlalchemy import (
    delete,
    select,
)



class SearchIndexRepository(
    BaseRepository[SearchIndex],
):
    """
    Repository for search indexes.
    """


    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            SearchIndex,
        )



    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[SearchIndex]:
        """
        Return all searchable objects
        inside a case.
        """

        result = self.session.execute(
            select(SearchIndex)
            .where(
                SearchIndex.case_id == case_id
            )
        )


        return list(
            result.scalars().all()
        )



    def search_content(
        self,
        query: str,
        case_id: UUID | None = None,
    ) -> list[SearchIndex]:
        """
        Simple text search.
        """

        statement = (
            select(SearchIndex)
            .where(
                SearchIndex.content.contains(
                    query
                )
            )
        )


        if case_id:

            statement = statement.where(
                SearchIndex.case_id == case_id
            )


        result = self.session.execute(
            statement
        )


        return list(
            result.scalars().all()
        )



    def get_by_object(
        self,
        object_type: SearchObjectType,
        object_id: UUID,
    ) -> SearchIndex | None:
        """
        Find indexed object.
        """

        result = self.session.execute(
            select(SearchIndex)
            .where(
                SearchIndex.object_type
                == object_type,
                SearchIndex.object_id
                == object_id,
            )
        )


        return result.scalar_one_or_none()

        # ==========================================================
    # Delete
    # ==========================================================

    def delete_by_object(
        self,
        *,
        object_type: SearchObjectType,
        object_id: UUID,
    ) -> int:
        """
        Delete SearchIndex belonging to one domain object.

        Related semantic embeddings should be removed
        before calling this method.
        """

        statement = (
            delete(
                SearchIndex
            )
            .where(
                SearchIndex.object_type
                == object_type
            )
            .where(
                SearchIndex.object_id
                == object_id
            )
        )

        result = (
            self.session.execute(
                statement
            )
        )

        return int(
            result.rowcount
            or 0
        )