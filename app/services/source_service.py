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
    ):
        self.repository = SourceRepository(
            session
        )

    def create_source(
        self,
        case_id: UUID,
        name: str,
        source_type: SourceType,
        path: str | None = None,
        description: str | None = None,
    ) -> Source:
        """
        Create new data source.
        """

        source = Source(
            case_id=case_id,
            name=name,
            source_type=source_type,
            original_path=path,
            description=description,
       )

        return self.repository.create(
            source
        )

    def get_source(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Get source by id.
        """

        return self.repository.get(
            source_id
        )

    def get_case_sources(
        self,
        case_id: UUID,
    ) -> list[Source]:
        """
        Return all sources
        belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )

    def mark_processing(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as processing.
        """

        source = self.repository.get(
            source_id
        )

        if source is None:
            return None

        source.status = SourceStatus.PROCESSING

        self.repository.session.flush()

        return source

    def mark_completed(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as completed.
        """

        source = self.repository.get(
            source_id
        )

        if source is None:
            return None

        source.status = SourceStatus.COMPLETED

        self.repository.session.flush()

        return source

    def mark_failed(
        self,
        source_id: UUID,
    ) -> Source | None:
        """
        Mark source as failed.
        """

        source = self.repository.get(
            source_id
        )

        if source is None:
            return None

        source.status = SourceStatus.FAILED

        self.repository.session.flush()

        return source

    def delete_source(
        self,
        source_id: UUID,
    ) -> bool:
        """
        Soft delete source.
        """

        source = self.repository.get(
            source_id
        )

        if source is None:
            return False

        source.soft_delete()

        self.repository.session.flush()

        return True