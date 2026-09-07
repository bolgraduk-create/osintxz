"""
Face profile repository.

Provides database operations for persistent
Face Memory profiles.

Responsibilities:

- create face profiles
- retrieve profiles
- list active profiles
- update profile metadata
- soft-delete profiles

Does NOT:

- calculate face embeddings
- compare faces
- perform identity decisions
- commit or rollback transactions
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.models.face_profile import (
    FaceProfile,
)

from app.repositories.base_repository import (
    BaseRepository,
)


class FaceProfileRepository(
    BaseRepository[FaceProfile],
):
    """
    Repository for FaceProfile.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        super().__init__(
            session,
            FaceProfile,
        )

    # ==========================================================
    # Creation
    # ==========================================================

    def create(
        self,
        *,
        label: str,
        description: str | None = None,
        status: str = "active",
    ) -> FaceProfile:
        """
        Create one persistent face profile.

        Does not commit the transaction.
        """

        normalized_label = str(
            label
            or ""
        ).strip()

        if not normalized_label:

            raise ValueError(
                "Face profile label cannot be empty."
            )

        normalized_status = str(
            status
            or "active"
        ).strip().lower()

        if not normalized_status:

            normalized_status = "active"

        normalized_description = (
            str(
                description
            ).strip()
            if description is not None
            else None
        )

        if normalized_description == "":

            normalized_description = None

        profile = FaceProfile(
            label=normalized_label,
            description=normalized_description,
            status=normalized_status,
        )

        self.session.add(
            profile
        )

        self.session.flush()

        return profile

    # ==========================================================
    # Retrieval
    # ==========================================================

    def get_active(
        self,
        profile_id: UUID,
    ) -> FaceProfile | None:
        """
        Return one active, non-deleted profile.
        """

        result = self.session.execute(
            select(
                FaceProfile
            )
            .where(
                FaceProfile.id
                == profile_id,
                FaceProfile.deleted_at
                .is_(None),
            )
            .limit(
                1
            )
        )

        return (
            result
            .scalar_one_or_none()
        )

    def get_with_embeddings(
        self,
        profile_id: UUID,
    ) -> FaceProfile | None:
        """
        Return one active profile together
        with its stored embeddings.
        """

        result = self.session.execute(
            select(
                FaceProfile
            )
            .options(
                selectinload(
                    FaceProfile.embeddings
                )
            )
            .where(
                FaceProfile.id
                == profile_id,
                FaceProfile.deleted_at
                .is_(None),
            )
            .limit(
                1
            )
        )

        return (
            result
            .scalar_one_or_none()
        )

    def list_active(
        self,
    ) -> list[FaceProfile]:
        """
        Return all active, non-deleted
        face profiles.
        """

        result = self.session.execute(
            select(
                FaceProfile
            )
            .where(
                FaceProfile.deleted_at
                .is_(None),
                FaceProfile.status
                == "active",
            )
            .order_by(
                FaceProfile.created_at
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    def find_by_label(
        self,
        label: str,
    ) -> list[FaceProfile]:
        """
        Find active profiles by exact
        case-insensitive label.
        """

        normalized_label = str(
            label
            or ""
        ).strip()

        if not normalized_label:

            return []

        result = self.session.execute(
            select(
                FaceProfile
            )
            .where(
                FaceProfile.deleted_at
                .is_(None),
                FaceProfile.label
                .ilike(
                    normalized_label
                ),
            )
            .order_by(
                FaceProfile.created_at
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    # ==========================================================
    # Updates
    # ==========================================================

    def rename(
        self,
        profile_id: UUID,
        label: str,
    ) -> FaceProfile | None:
        """
        Rename a face profile.
        """

        profile = self.get_active(
            profile_id
        )

        if profile is None:

            return None

        normalized_label = str(
            label
            or ""
        ).strip()

        if not normalized_label:

            raise ValueError(
                "Face profile label cannot be empty."
            )

        profile.label = normalized_label

        self.session.flush()

        return profile

    def update_description(
        self,
        profile_id: UUID,
        description: str | None,
    ) -> FaceProfile | None:
        """
        Update profile description.
        """

        profile = self.get_active(
            profile_id
        )

        if profile is None:

            return None

        normalized_description = (
            str(
                description
            ).strip()
            if description is not None
            else None
        )

        if normalized_description == "":

            normalized_description = None

        profile.description = (
            normalized_description
        )

        self.session.flush()

        return profile

    def set_status(
        self,
        profile_id: UUID,
        status: str,
    ) -> FaceProfile | None:
        """
        Change profile status.
        """

        profile = self.get_active(
            profile_id
        )

        if profile is None:

            return None

        normalized_status = str(
            status
            or ""
        ).strip().lower()

        if not normalized_status:

            raise ValueError(
                "Face profile status cannot be empty."
            )

        profile.status = (
            normalized_status
        )

        self.session.flush()

        return profile

    # ==========================================================
    # Soft deletion
    # ==========================================================

    def soft_delete_profile(
        self,
        profile_id: UUID,
    ) -> bool:
        """
        Soft-delete one profile.
        """

        profile = self.get_active(
            profile_id
        )

        if profile is None:

            return False

        profile.soft_delete()

        self.session.flush()

        return True