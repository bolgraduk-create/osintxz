"""
Document service.

Contains business logic related
to documents stored inside cases.

Examples:

- PDF files
- DOCX files
- Text documents
- Imported reports

Search lifecycle:

Document
    ↓
DocumentRepository
    ↓
SearchIndexingService
    ↓
SearchIndex

Semantic embeddings are generated separately so
high-volume imports do not perform one embedding
request for every document.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentType,
)

from app.repositories.document_repository import (
    DocumentRepository,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)


class DocumentService:
    """
    Service for managing documents.
    """

    def __init__(
        self,
        session: Session,
        *,
        search_indexing_service: (
            SearchIndexingService
            | None
        ) = None,
    ) -> None:

        self.repository = (
            DocumentRepository(
                session
            )
        )

        self.search_indexing_service = (
            search_indexing_service
        )

    # ======================================================
    # Create
    # ======================================================

    def create_document(
        self,
        case_id: UUID,
        title: str,
        document_type: DocumentType,
        source_id: UUID | None = None,
        file_path: str | None = None,
        content: str | None = None,
        description: str | None = None,
        *,
        update_search_index: bool = True,
    ) -> Document:
        """
        Create new document.
        """

        document = Document(
            case_id=case_id,
            source_id=source_id,
            title=title,
            document_type=document_type,
            file_path=file_path,
            content=content,
            description=description,
        )

        document = (
            self.repository.create(
                document
            )
        )

        if (
            update_search_index
            and self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    document
                )

        return document

    # ======================================================
    # Read
    # ======================================================

    def get_document(
        self,
        document_id: UUID,
    ) -> Document | None:
        """
        Get document by id.
        """

        return (
            self.repository.get(
                document_id
            )
        )

    def get_case_documents(
        self,
        case_id: UUID,
    ) -> list[Document]:
        """
        Return all documents belonging to a case.
        """

        return (
            self.repository.get_by_case(
                case_id
            )
        )

    # ======================================================
    # Update
    # ======================================================

    def update_content(
        self,
        document_id: UUID,
        content: str,
    ) -> Document | None:
        """
        Update document text content and refresh
        its textual search representation.

        Existing semantic embedding is invalidated.
        """

        document = (
            self.repository.get(
                document_id
            )
        )

        if document is None:

            return None

        document.content = content

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    document
                )

        return document

    def update_hash(
        self,
        document_id: UUID,
        sha256: str,
    ) -> Document | None:
        """
        Store document hash.

        Hash changes currently remain a persistence
        operation. Search reindexing is unnecessary
        unless SearchIndexBuilder includes the hash
        in the searchable representation.
        """

        document = (
            self.repository.get(
                document_id
            )
        )

        if document is None:

            return None

        document.sha256 = sha256

        self.repository.session.flush()

        return document

    # ======================================================
    # Explicit search refresh
    # ======================================================

    def refresh_search(
        self,
        document_id: UUID,
        *,
        include_embedding: bool = True,
    ) -> bool:
        """
        Refresh search representation for one document.
        """

        if (
            self.search_indexing_service
            is None
        ):

            return False

        document = (
            self.repository.get(
                document_id
            )
        )

        if document is None:

            return False

        self.search_indexing_service \
            .index_object(
                document,
                include_embedding=(
                    include_embedding
                ),
                force_embedding=(
                    include_embedding
                ),
            )

        return True

    # ======================================================
    # Delete
    # ======================================================

    def delete_document(
        self,
        document_id: UUID,
    ) -> bool:
        """
        Soft delete document and remove its search
        representations.
        """

        document = (
            self.repository.get(
                document_id
            )
        )

        if document is None:

            return False

        document.soft_delete()

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .remove_object(
                    document
                )

        return True