"""
Face embedding repository.

Provides persistent storage and vector search
for SFace embeddings.

Responsibilities:

- store VECTOR(128) face embeddings
- retrieve embeddings by evidence/profile
- prevent duplicate evidence-face observations
- search nearest face embeddings
- calculate cosine distance

Does NOT:

- generate embeddings
- detect faces
- decide real-world identity
- create user-facing conclusions
- commit or rollback transactions
"""

from __future__ import annotations

import math

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.models.face_embedding import (
    FaceEmbedding,
)

from app.repositories.base_repository import (
    BaseRepository,
)


class FaceEmbeddingRepository(
    BaseRepository[FaceEmbedding],
):
    """
    Repository for FaceEmbedding.
    """

    EMBEDDING_DIMENSION = 128

    def __init__(
        self,
        session: Session,
    ) -> None:

        super().__init__(
            session,
            FaceEmbedding,
        )

    # ==========================================================
    # Creation
    # ==========================================================

    def create(
        self,
        *,
        evidence_id: UUID,
        case_id: UUID,
        face_id: str,
        face_index: int,
        embedding: list[float],
        profile_id: UUID | None = None,
        recognizer: str = "sface",
        detector: str = "yunet",
        detection_confidence: float | None = None,
        bbox_json: str | None = None,
        source_metadata_json: str | None = None,
    ) -> FaceEmbedding:
        """
        Store one face embedding.

        Does not commit.
        """

        normalized_face_id = str(
            face_id
            or ""
        ).strip()

        if not normalized_face_id:

            raise ValueError(
                "face_id cannot be empty."
            )

        normalized_embedding = (
            self._normalize_embedding(
                embedding
            )
        )

        existing = (
            self.get_by_evidence_face(
                evidence_id=evidence_id,
                face_id=(
                    normalized_face_id
                ),
            )
        )

        if existing is not None:

            raise ValueError(
                (
                    "A face embedding already exists "
                    "for this evidence and face_id."
                )
            )

        observation = FaceEmbedding(
            profile_id=profile_id,
            evidence_id=evidence_id,
            case_id=case_id,
            face_id=normalized_face_id,
            face_index=int(
                face_index
            ),
            embedding=normalized_embedding,
            recognizer=str(
                recognizer
                or "sface"
            ).strip(),
            detector=str(
                detector
                or "yunet"
            ).strip(),
            detection_confidence=(
                float(
                    detection_confidence
                )
                if detection_confidence
                is not None
                else None
            ),
            bbox_json=bbox_json,
            source_metadata_json=(
                source_metadata_json
            ),
        )

        self.session.add(
            observation
        )

        self.session.flush()

        return observation

    # ==========================================================
    # Retrieval
    # ==========================================================

    def get_active(
        self,
        embedding_id: UUID,
    ) -> FaceEmbedding | None:
        """
        Return one active embedding.
        """

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.id
                == embedding_id,
                FaceEmbedding.deleted_at
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

    def get_by_evidence_face(
        self,
        *,
        evidence_id: UUID,
        face_id: str,
    ) -> FaceEmbedding | None:
        """
        Return one observation for a specific
        face inside one evidence item.
        """

        normalized_face_id = str(
            face_id
            or ""
        ).strip()

        if not normalized_face_id:

            return None

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.evidence_id
                == evidence_id,
                FaceEmbedding.face_id
                == normalized_face_id,
                FaceEmbedding.deleted_at
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

    def get_by_evidence(
        self,
        evidence_id: UUID,
    ) -> list[FaceEmbedding]:
        """
        Return all active face observations
        belonging to one evidence item.
        """

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.evidence_id
                == evidence_id,
                FaceEmbedding.deleted_at
                .is_(None),
            )
            .order_by(
                FaceEmbedding.face_index
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[FaceEmbedding]:
        """
        Return active face observations
        from one investigation.
        """

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.case_id
                == case_id,
                FaceEmbedding.deleted_at
                .is_(None),
            )
            .order_by(
                FaceEmbedding.created_at
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    def get_by_profile(
        self,
        profile_id: UUID,
    ) -> list[FaceEmbedding]:
        """
        Return all active observations assigned
        to one Face Memory profile.
        """

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.profile_id
                == profile_id,
                FaceEmbedding.deleted_at
                .is_(None),
            )
            .order_by(
                FaceEmbedding.created_at
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    def get_unassigned(
        self,
    ) -> list[FaceEmbedding]:
        """
        Return active face observations that
        have not been assigned to a profile.
        """

        result = self.session.execute(
            select(
                FaceEmbedding
            )
            .where(
                FaceEmbedding.profile_id
                .is_(None),
                FaceEmbedding.deleted_at
                .is_(None),
            )
            .order_by(
                FaceEmbedding.created_at
            )
        )

        return list(
            result
            .scalars()
            .all()
        )

    # ==========================================================
    # Profile assignment
    # ==========================================================

    def assign_profile(
        self,
        embedding_id: UUID,
        profile_id: UUID | None,
    ) -> FaceEmbedding | None:
        """
        Assign or unassign an observation
        from a Face Memory profile.
        """

        observation = self.get_active(
            embedding_id
        )

        if observation is None:

            return None

        observation.profile_id = (
            profile_id
        )

        self.session.flush()

        return observation

    # ==========================================================
    # Vector search
    # ==========================================================

    def find_similar(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        maximum_distance: float | None = None,
        exclude_embedding_id: UUID | None = None,
        exclude_evidence_id: UUID | None = None,
        profile_only: bool = False,
    ) -> list[
        tuple[
            FaceEmbedding,
            float,
        ]
    ]:
        """
        Return nearest stored embeddings by
        cosine distance.

        Smaller cosine distance means a closer
        numerical match.

        Cosine similarity can be calculated as:

            similarity = 1.0 - distance
        """

        normalized_embedding = (
            self._normalize_embedding(
                embedding
            )
        )

        normalized_limit = (
            self._normalize_limit(
                limit
            )
        )

        distance_expression = (
            FaceEmbedding
            .embedding
            .cosine_distance(
                normalized_embedding
            )
        )

        statement = (
            select(
                FaceEmbedding,
                distance_expression.label(
                    "distance"
                ),
            )
            .options(
                joinedload(
                    FaceEmbedding.profile
                )
            )
            .where(
                FaceEmbedding.deleted_at
                .is_(None)
            )
        )

        if (
            exclude_embedding_id
            is not None
        ):

            statement = (
                statement.where(
                    FaceEmbedding.id
                    != exclude_embedding_id
                )
            )

        if (
            exclude_evidence_id
            is not None
        ):

            statement = (
                statement.where(
                    FaceEmbedding.evidence_id
                    != exclude_evidence_id
                )
            )

        if profile_only:

            statement = (
                statement.where(
                    FaceEmbedding.profile_id
                    .is_not(
                        None
                    )
                )
            )

        if (
            maximum_distance
            is not None
        ):

            normalized_distance = (
                self._normalize_distance(
                    maximum_distance
                )
            )

            statement = (
                statement.where(
                    distance_expression
                    <= normalized_distance
                )
            )

        statement = (
            statement
            .order_by(
                distance_expression
            )
            .limit(
                normalized_limit
            )
        )

        rows = (
            self.session.execute(
                statement
            )
            .all()
        )

        results: list[
            tuple[
                FaceEmbedding,
                float,
            ]
        ] = []

        for observation, distance in rows:

            try:

                normalized_result_distance = (
                    float(
                        distance
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if not math.isfinite(
                normalized_result_distance
            ):

                continue

            results.append(
                (
                    observation,
                    normalized_result_distance,
                )
            )

        return results

    # ==========================================================
    # Soft deletion
    # ==========================================================

    def soft_delete_embedding(
        self,
        embedding_id: UUID,
    ) -> bool:
        """
        Soft-delete one face observation.
        """

        observation = self.get_active(
            embedding_id
        )

        if observation is None:

            return False

        observation.soft_delete()

        self.session.flush()

        return True

    # ==========================================================
    # Validation
    # ==========================================================

    @classmethod
    def _normalize_embedding(
        cls,
        embedding: list[float],
    ) -> list[float]:
        """
        Validate a SFace VECTOR(128).

        Vectors are expected to have already
        been L2-normalized by the analyzer.
        """

        if not isinstance(
            embedding,
            (
                list,
                tuple,
            ),
        ):

            raise TypeError(
                "embedding must be a list or tuple."
            )

        if (
            len(
                embedding
            )
            != cls.EMBEDDING_DIMENSION
        ):

            raise ValueError(
                (
                    "Face embedding must contain "
                    f"{cls.EMBEDDING_DIMENSION} values."
                )
            )

        result: list[
            float
        ] = []

        for index, value in enumerate(
            embedding
        ):

            try:

                numeric_value = float(
                    value
                )

            except (
                TypeError,
                ValueError,
            ) as error:

                raise ValueError(
                    (
                        "Face embedding value "
                        f"{index} is not numeric."
                    )
                ) from error

            if not math.isfinite(
                numeric_value
            ):

                raise ValueError(
                    (
                        "Face embedding contains "
                        "non-finite values."
                    )
                )

            result.append(
                numeric_value
            )

        norm = math.sqrt(
            sum(
                value
                * value
                for value
                in result
            )
        )

        if norm <= 0.0:

            raise ValueError(
                "Face embedding has zero norm."
            )

        # Normalize defensively even though
        # FaceEmbeddingAnalyzer already does this.

        return [
            value
            / norm
            for value
            in result
        ]

    @staticmethod
    def _normalize_limit(
        limit: int,
    ) -> int:

        if isinstance(
            limit,
            bool,
        ):

            raise TypeError(
                "limit must be an integer."
            )

        try:

            normalized = int(
                limit
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "limit must be an integer."
            ) from error

        if normalized <= 0:

            raise ValueError(
                "limit must be greater than zero."
            )

        if normalized > 1000:

            raise ValueError(
                "limit must not exceed 1000."
            )

        return normalized

    @staticmethod
    def _normalize_distance(
        distance: float,
    ) -> float:

        try:

            normalized = float(
                distance
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "maximum_distance must be numeric."
            ) from error

        if not math.isfinite(
            normalized
        ):

            raise ValueError(
                "maximum_distance must be finite."
            )

        if not (
            0.0
            <= normalized
            <= 2.0
        ):

            raise ValueError(
                (
                    "Cosine distance must be "
                    "between 0.0 and 2.0."
                )
            )

        return normalized