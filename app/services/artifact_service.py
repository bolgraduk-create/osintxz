"""
Artifact service.

Contains business logic
for investigation artifacts.

Search lifecycle is synchronized through
SearchIndexingService.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.artifact import (
    Artifact,
    ArtifactType,
)

from app.repositories.artifact_repository import (
    ArtifactRepository,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)


class ArtifactService:
    """
    Service for managing artifacts.
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
            ArtifactRepository(
                session
            )
        )

        self.search_indexing_service = (
            search_indexing_service
        )

    # ======================================================
    # Create
    # ======================================================

    def create_artifact(
        self,
        case_id: UUID,
        artifact_type: ArtifactType,
        name: str,
        file_path: str | None = None,
        mime_type: str | None = None,
        metadata_json: str | None = None,
        description: str | None = None,
        *,
        update_search_index: bool = True,
    ) -> Artifact:
        """
        Create artifact.
        """

        artifact = Artifact(
            case_id=case_id,
            artifact_type=artifact_type,
            name=name,
            file_path=file_path,
            mime_type=mime_type,
            metadata_json=metadata_json,
            description=description,
        )

        artifact = (
            self.repository.create(
                artifact
            )
        )

        if (
            update_search_index
            and self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    artifact
                )

        return artifact

    # ======================================================
    # Read
    # ======================================================

    def get_artifact(
        self,
        artifact_id: UUID,
    ) -> Artifact | None:
        """
        Get artifact by id.
        """

        return (
            self.repository.get(
                artifact_id
            )
        )

    def get_case_artifacts(
        self,
        case_id: UUID,
    ) -> list[Artifact]:
        """
        Return case artifacts.
        """

        return (
            self.repository.get_by_case(
                case_id
            )
        )

    # ======================================================
    # Update
    # ======================================================

    def update_metadata(
        self,
        artifact_id: UUID,
        metadata_json: str,
    ) -> Artifact | None:
        """
        Update artifact metadata.

        SearchIndexBuilder decides whether metadata is
        part of the searchable representation.
        """

        artifact = (
            self.repository.get(
                artifact_id
            )
        )

        if artifact is None:

            return None

        artifact.metadata_json = (
            metadata_json
        )

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    artifact
                )

        return artifact

    # ======================================================
    # Explicit search refresh
    # ======================================================

    def refresh_search(
        self,
        artifact_id: UUID,
        *,
        include_embedding: bool = True,
    ) -> bool:
        """
        Refresh search representation for one artifact.
        """

        if (
            self.search_indexing_service
            is None
        ):

            return False

        artifact = (
            self.repository.get(
                artifact_id
            )
        )

        if artifact is None:

            return False

        self.search_indexing_service \
            .index_object(
                artifact,
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

    def delete_artifact(
        self,
        artifact_id: UUID,
    ) -> bool:
        """
        Soft delete artifact and remove its search
        representations.
        """

        artifact = (
            self.repository.get(
                artifact_id
            )
        )

        if artifact is None:

            return False

        artifact.soft_delete()

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .remove_object(
                    artifact
                )

        return True