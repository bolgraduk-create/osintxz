"""
Document service.

Contains business logic related
to documents stored inside cases.

Examples:

- PDF files
- DOCX files
- Text documents
- Imported reports
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


class DocumentService:
    """
    Service for managing documents.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = DocumentRepository(
            session
        )


    def create_document(
        self,
        case_id: UUID,
        title: str,
        document_type: DocumentType,
        source_id: UUID | None = None,
        file_path: str | None = None,
        content: str | None = None,
        description: str | None = None,
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

        return self.repository.create(
            document
        )


    def get_document(
        self,
        document_id: UUID,
    ) -> Document | None:
        """
        Get document by id.
        """

        return self.repository.get(
            document_id
        )


    def get_case_documents(
        self,
        case_id: UUID,
    ) -> list[Document]:
        """
        Return all documents
        belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )


    def update_content(
        self,
        document_id: UUID,
        content: str,
    ) -> Document | None:
        """
        Update document text content.
        """

        document = self.repository.get(
            document_id
        )

        if document is None:
            return None

        document.content = content

        self.repository.session.flush()

        return document


    def update_hash(
        self,
        document_id: UUID,
        sha256: str,
    ) -> Document | None:
        """
        Store document hash.
        """

        document = self.repository.get(
            document_id
        )

        if document is None:
            return None

        document.sha256 = sha256

        self.repository.session.flush()

        return document


    def delete_document(
        self,
        document_id: UUID,
    ) -> bool:
        """
        Soft delete document.
        """

        document = self.repository.get(
            document_id
        )

        if document is None:
            return False

        document.soft_delete()

        self.repository.session.flush()

        return True