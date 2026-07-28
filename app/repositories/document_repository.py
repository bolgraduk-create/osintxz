"""
Document repository.

Provides database operations
for stored documents.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentType,
)
from app.repositories.base_repository import (
    BaseRepository,
)


class DocumentRepository(
    BaseRepository[Document],
):
    """
    Repository for Document model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Document,
        )

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Document]:
        """
        Return documents belonging to a case.
        """

        result = self.session.execute(
            select(Document)
            .where(
                Document.case_id == case_id,
            )
            .order_by(Document.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_source(
        self,
        source_id: UUID,
    ) -> list[Document]:
        """
        Return documents imported from a source.
        """

        result = self.session.execute(
            select(Document)
            .where(
                Document.source_id == source_id,
            )
            .order_by(Document.created_at)
        )

        return list(
            result.scalars().all()
        )

    def get_by_type(
        self,
        document_type: DocumentType,
    ) -> list[Document]:
        """
        Return documents of the specified type.
        """

        result = self.session.execute(
            select(Document)
            .where(
                Document.document_type == document_type,
            )
            .order_by(Document.created_at)
        )

        return list(
            result.scalars().all()
        )

    def find_by_hash(
        self,
        sha256: str,
    ) -> Document | None:
        """
        Find document by SHA256 hash.
        """

        result = self.session.execute(
            select(Document)
            .where(
                Document.sha256 == sha256,
            )
        )

        return result.scalar_one_or_none()

    def search_content(
        self,
        query: str,
    ) -> list[Document]:
        """
        Search documents by content.
        """

        result = self.session.execute(
            select(Document)
            .where(
                Document.content.ilike(
                    f"%{query}%"
                )
            )
            .order_by(Document.created_at)
        )

        return list(
            result.scalars().all()
        )