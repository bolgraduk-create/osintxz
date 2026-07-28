"""
Artifact repository.

Provides database operations
for investigation artifacts.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import (
    Artifact,
    ArtifactType,
)

from app.repositories.base_repository import (
    BaseRepository,
)



class ArtifactRepository(
    BaseRepository[Artifact],
):
    """
    Repository for artifacts.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Artifact,
        )


    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Artifact]:
        """
        Return artifacts
        belonging to case.
        """

        result = self.session.execute(
            select(Artifact)
            .where(
                Artifact.case_id == case_id
            )
        )

        return list(
            result.scalars().all()
        )


    def get_by_type(
        self,
        artifact_type: ArtifactType,
    ) -> list[Artifact]:
        """
        Find artifacts by type.
        """

        result = self.session.execute(
            select(Artifact)
            .where(
                Artifact.artifact_type
                == artifact_type
            )
        )

        return list(
            result.scalars().all()
        )


    def get_case_artifact_types(
        self,
        case_id: UUID,
    ) -> list[ArtifactType]:
        """
        Return artifact types
        used in case.
        """

        result = self.session.execute(
            select(
                Artifact.artifact_type
            )
            .where(
                Artifact.case_id == case_id
            )
            .distinct()
        )

        return list(
            result.scalars().all()
        )