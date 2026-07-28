"""
Search service.

Business logic for
investigation search.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.search_index import (
    SearchIndex,
    SearchObjectType,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)



class SearchService:
    """
    Service for search operations.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = SearchIndexRepository(
            session
        )



    def index_object(
        self,
        case_id: UUID,
        object_type: SearchObjectType,
        object_id: UUID,
        title: str,
        content: str,
    ) -> SearchIndex:
        """
        Add object to search index.
        """

        index = SearchIndex(
            case_id=case_id,
            object_type=object_type,
            object_id=object_id,
            title=title,
            content=content,
        )

        return self.repository.create(
            index
        )



    def get_index(
        self,
        object_type: SearchObjectType,
        object_id: UUID,
    ) -> SearchIndex | None:
        """
        Get indexed object.
        """

        return self.repository.get_by_object(
            object_type,
            object_id,
        )



    def search(
        self,
        query: str,
        case_id: UUID | None = None,
    ) -> list[SearchIndex]:
        """
        Search indexed content.
        """

        return self.repository.search_content(
            query,
            case_id,
        )



    def delete_index(
        self,
        index_id: UUID,
    ) -> bool:
        """
        Delete search index.
        """

        index = self.repository.get(
            index_id
        )


        if index is None:
            return False


        index.soft_delete()

        self.repository.session.flush()

        return True