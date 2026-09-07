"""
Source service.

Contains business logic related
to investigation data sources.

Examples:

- Telegram export
- JSON file
- PDF
- Database dump
- API source
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.source import (
    Source,
    SourceStatus,
    SourceType,
)

from app.repositories.source_repository import (
    SourceRepository,
)


class SourceService:
    """
    Service for managing sources.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.repository = SourceRepository(
            session
        )

    # ==========================================================
    # Creation
    # ==========================================================

    def create_source(
        self,
        case_id: UUID,
        name: str,
        source_type: SourceType,
        path: str | None = None,
        description: str | None = None,
    ) -> Source:
        """
        Create a new pending data source.
        """

        source = Source(
            case_id=case_id,
            name=name,
            source_type=source_type,
            status=SourceStatus.PENDING,
            original_path=path,
            description=description,
        )

        return self.repository.create(
            source
        )

    # ==========================================================
    # Reading
    # ==========================================================

    def get_source(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Get source by ID.
        """

        return self.repository.get(
            source_id
        )

    def get_case_sources(
        self,
        case_id: UUID,
    ) -> list[Source]:
        """
        Return all sources belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )

    # ==========================================================
    # Status
    # ==========================================================

    def mark_importing(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as currently importing.
        """

        return self.repository.update_status(
            source_id,
            SourceStatus.IMPORTING,
        )

    def mark_imported(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as successfully imported.

        The original material is stored, but further processing
        may still be required.
        """

        return self.repository.update_status(
            source_id,
            SourceStatus.IMPORTED,
        )

    def mark_ready(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as fully processed and ready.
        """

        return self.repository.update_status(
            source_id,
            SourceStatus.READY,
        )

    def mark_failed(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as failed.
        """

        return self.repository.update_status(
            source_id,
            SourceStatus.FAILED,
        )

    # ==========================================================
    # Compatibility methods
    # ==========================================================

    def mark_processing(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Compatibility alias for older callers.

        PROCESSING is represented by IMPORTING
        in the current database schema.
        """

        return self.mark_importing(
            source_id
        )

    def mark_completed(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Compatibility alias for older callers.

        COMPLETED is represented by IMPORTED
        until all processing stages finish.
        """

        return self.mark_imported(
            source_id
        )

    # ==========================================================
    # Deletion
    # ==========================================================

    def delete_source(
        self,
        source_id: UUID,
    ) -> bool:
        """
        Soft-delete source.
        """

        source = self.repository.get(
            source_id
        )

        if source is None:

            return False

        source.soft_delete()

        self.repository.session.flush()

        return True