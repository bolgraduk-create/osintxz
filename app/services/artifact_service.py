"""
Artifact service.

Contains business logic
for investigation artifacts.
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



class ArtifactService:
    """
    Service for managing artifacts.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = ArtifactRepository(
            session
        )


    def create_artifact(
        self,
        case_id: UUID,
        artifact_type: ArtifactType,
        name: str,
        file_path: str | None = None,
        mime_type: str | None = None,
        metadata_json: str | None = None,
        description: str | None = None,
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

        return self.repository.create(
            artifact
        )


    def get_artifact(
        self,
        artifact_id: UUID,
    ) -> Artifact | None:
        """
        Get artifact by id.
        """

        return self.repository.get(
            artifact_id
        )


    def get_case_artifacts(
        self,
        case_id: UUID,
    ) -> list[Artifact]:
        """
        Return case artifacts.
        """

        return self.repository.get_by_case(
            case_id
        )


    def update_metadata(
        self,
        artifact_id: UUID,
        metadata_json: str,
    ) -> Artifact | None:
        """
        Update artifact metadata.
        """

        artifact = self.repository.get(
            artifact_id
        )

        if artifact is None:
            return None


        artifact.metadata_json = metadata_json

        self.repository.session.flush()

        return artifact


    def delete_artifact(
        self,
        artifact_id: UUID,
    ) -> bool:
        """
        Soft delete artifact.
        """

        artifact = self.repository.get(
            artifact_id
        )

        if artifact is None:
            return False


        artifact.soft_delete()

        self.repository.session.flush()

        return True