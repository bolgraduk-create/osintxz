"""
Face Memory service.

Provides the application-level API for
persistent face-memory operations.

Architecture:

UI / Controllers
        ↓
FaceMemoryService
        ↓
FaceProfileRepository
FaceEmbeddingRepository
        ↓
PostgreSQL + pgvector

Responsibilities:

- create and manage face profiles
- persist SFace embeddings
- assign observations to profiles
- search similar stored faces
- convert vector distance into useful match data
- prevent repository logic from leaking into UI

Does NOT:

- detect faces
- generate embeddings
- identify a real-world person automatically
- commit or rollback transactions
"""

from __future__ import annotations

import json
import math

from typing import Any
from uuid import UUID

from app.models.face_embedding import (
    FaceEmbedding,
)

from app.models.face_profile import (
    FaceProfile,
)

from app.repositories.face_embedding_repository import (
    FaceEmbeddingRepository,
)

from app.repositories.face_profile_repository import (
    FaceProfileRepository,
)


class FaceMemoryService:
    """
    Application service for persistent
    face-memory operations.
    """

    DEFAULT_SEARCH_LIMIT = 10

    # Conservative application-level threshold.
    #
    # This is NOT an identity guarantee.
    #
    # Similarity returned by this service is:
    #
    #     1 - cosine_distance
    #
    DEFAULT_MINIMUM_SIMILARITY = 0.40

    def __init__(
        self,
        profile_repository: FaceProfileRepository,
        embedding_repository: FaceEmbeddingRepository,
    ) -> None:

        self.profile_repository = (
            profile_repository
        )

        self.embedding_repository = (
            embedding_repository
        )

    # ==========================================================
    # Profiles
    # ==========================================================

    def create_profile(
        self,
        *,
        label: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a persistent Face Memory profile.

        The profile represents a user-managed
        grouping of face observations.
        """

        profile = (
            self.profile_repository
            .create(
                label=label,
                description=description,
            )
        )

        return (
            self._profile_summary(
                profile
            )
        )

    def get_profile(
        self,
        profile_id: str | UUID,
    ) -> dict[str, Any] | None:
        """
        Return one profile together with
        its active embeddings.
        """

        normalized_id = (
            self._normalize_uuid(
                profile_id,
                field_name="profile_id",
            )
        )

        profile = (
            self.profile_repository
            .get_with_embeddings(
                normalized_id
            )
        )

        if profile is None:

            return None

        active_embeddings = [
            embedding
            for embedding
            in profile.embeddings
            if getattr(
                embedding,
                "deleted_at",
                None,
            )
            is None
        ]

        return {
            **self._profile_summary(
                profile
            ),
            "embedding_count": len(
                active_embeddings
            ),
            "embeddings": [
                self._embedding_summary(
                    embedding
                )
                for embedding
                in active_embeddings
            ],
        }

    def list_profiles(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return active Face Memory profiles.
        """

        profiles = (
            self.profile_repository
            .list_active()
        )

        return [
            self._profile_summary(
                profile
            )
            for profile
            in profiles
        ]

    def rename_profile(
        self,
        profile_id: str | UUID,
        *,
        label: str,
    ) -> dict[str, Any] | None:
        """
        Rename one Face Memory profile.
        """

        normalized_id = (
            self._normalize_uuid(
                profile_id,
                field_name="profile_id",
            )
        )

        profile = (
            self.profile_repository
            .rename(
                normalized_id,
                label,
            )
        )

        if profile is None:

            return None

        return (
            self._profile_summary(
                profile
            )
        )

    def delete_profile(
        self,
        profile_id: str | UUID,
    ) -> bool:
        """
        Soft-delete a Face Memory profile.
        """

        normalized_id = (
            self._normalize_uuid(
                profile_id,
                field_name="profile_id",
            )
        )

        return (
            self.profile_repository
            .soft_delete_profile(
                normalized_id
            )
        )

    # ==========================================================
    # Face observations
    # ==========================================================

    def remember_face(
        self,
        *,
        evidence_id: str | UUID,
        case_id: str | UUID,
        face_id: str,
        face_index: int,
        embedding: list[float],
        profile_id: str | UUID | None = None,
        recognizer: str = "sface",
        detector: str = "yunet",
        detection_confidence: float | None = None,
        bbox: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Persist one face observation.

        Existing evidence/face observations are
        returned instead of duplicated.
        """

        normalized_evidence_id = (
            self._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        normalized_case_id = (
            self._normalize_uuid(
                case_id,
                field_name="case_id",
            )
        )

        normalized_profile_id = (
            self._normalize_optional_uuid(
                profile_id,
                field_name="profile_id",
            )
        )

        normalized_face_id = str(
            face_id
            or ""
        ).strip()

        if not normalized_face_id:

            raise ValueError(
                "face_id cannot be empty."
            )

        existing = (
            self.embedding_repository
            .get_by_evidence_face(
                evidence_id=(
                    normalized_evidence_id
                ),
                face_id=(
                    normalized_face_id
                ),
            )
        )

        if existing is not None:

            if (
                normalized_profile_id
                is not None
                and existing.profile_id
                != normalized_profile_id
            ):

                existing = (
                    self.embedding_repository
                    .assign_profile(
                        existing.id,
                        normalized_profile_id,
                    )
                )

            if existing is None:

                raise RuntimeError(
                    "Existing face observation disappeared."
                )

            return {
                **self._embedding_summary(
                    existing
                ),
                "created": False,
            }

        observation = (
            self.embedding_repository
            .create(
                evidence_id=(
                    normalized_evidence_id
                ),
                case_id=(
                    normalized_case_id
                ),
                face_id=(
                    normalized_face_id
                ),
                face_index=(
                    int(
                        face_index
                    )
                ),
                embedding=embedding,
                profile_id=(
                    normalized_profile_id
                ),
                recognizer=recognizer,
                detector=detector,
                detection_confidence=(
                    detection_confidence
                ),
                bbox_json=(
                    self._encode_optional_json(
                        bbox
                    )
                ),
                source_metadata_json=(
                    self._encode_optional_json(
                        source_metadata
                    )
                ),
            )
        )

        return {
            **self._embedding_summary(
                observation
            ),
            "created": True,
        }

    def assign_face_to_profile(
        self,
        embedding_id: str | UUID,
        profile_id: str | UUID | None,
    ) -> dict[str, Any] | None:
        """
        Assign or unassign a persistent
        face observation.
        """

        normalized_embedding_id = (
            self._normalize_uuid(
                embedding_id,
                field_name="embedding_id",
            )
        )

        normalized_profile_id = (
            self._normalize_optional_uuid(
                profile_id,
                field_name="profile_id",
            )
        )

        if normalized_profile_id is not None:

            profile = (
                self.profile_repository
                .get_active(
                    normalized_profile_id
                )
            )

            if profile is None:

                raise LookupError(
                    "Face profile was not found: "
                    f"{normalized_profile_id}"
                )

        observation = (
            self.embedding_repository
            .assign_profile(
                normalized_embedding_id,
                normalized_profile_id,
            )
        )

        if observation is None:

            return None

        return (
            self._embedding_summary(
                observation
            )
        )

    def get_evidence_faces(
        self,
        evidence_id: str | UUID,
    ) -> list[dict[str, Any]]:
        """
        Return persistent face observations
        for one evidence item.
        """

        normalized_id = (
            self._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        observations = (
            self.embedding_repository
            .get_by_evidence(
                normalized_id
            )
        )

        return [
            self._embedding_summary(
                observation
            )
            for observation
            in observations
        ]

    # ==========================================================
    # Similarity search
    # ==========================================================

    def search_face(
        self,
        embedding: list[float],
        *,
        minimum_similarity: float = (
            DEFAULT_MINIMUM_SIMILARITY
        ),
        limit: int = DEFAULT_SEARCH_LIMIT,
        exclude_embedding_id: (
            str | UUID | None
        ) = None,
        exclude_evidence_id: (
            str | UUID | None
        ) = None,
        profile_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search Face Memory for numerically
        similar SFace embeddings.

        Returned similarity is derived from
        cosine distance:

            similarity = 1 - distance

        This value is a visual matching score,
        not a proof of identity.
        """

        normalized_minimum = (
            self._normalize_similarity(
                minimum_similarity
            )
        )

        normalized_exclude_embedding_id = (
            self._normalize_optional_uuid(
                exclude_embedding_id,
                field_name=(
                    "exclude_embedding_id"
                ),
            )
        )

        normalized_exclude_evidence_id = (
            self._normalize_optional_uuid(
                exclude_evidence_id,
                field_name=(
                    "exclude_evidence_id"
                ),
            )
        )

        maximum_distance = (
            1.0
            - normalized_minimum
        )

        matches = (
            self.embedding_repository
            .find_similar(
                embedding,
                limit=limit,
                maximum_distance=(
                    maximum_distance
                ),
                exclude_embedding_id=(
                    normalized_exclude_embedding_id
                ),
                exclude_evidence_id=(
                    normalized_exclude_evidence_id
                ),
                profile_only=profile_only,
            )
        )

        results: list[
            dict[str, Any]
        ] = []

        for observation, distance in matches:

            similarity = (
                1.0
                - float(
                    distance
                )
            )

            similarity = max(
                -1.0,
                min(
                    similarity,
                    1.0,
                ),
            )

            results.append(
                {
                    "embedding": (
                        self._embedding_summary(
                            observation
                        )
                    ),
                    "distance": round(
                        float(
                            distance
                        ),
                        8,
                    ),
                    "similarity": round(
                        similarity,
                        8,
                    ),
                    "similarity_percent": round(
                        similarity
                        * 100.0,
                        2,
                    ),
                    "classification": (
                        self._classify_similarity(
                            similarity
                        )
                    ),
                    "profile": (
                        self._profile_summary(
                            observation.profile
                        )
                        if observation.profile
                        is not None
                        else None
                    ),
                }
            )

        return results

    def search_observation(
        self,
        embedding_id: str | UUID,
        *,
        minimum_similarity: float = (
            DEFAULT_MINIMUM_SIMILARITY
        ),
        limit: int = DEFAULT_SEARCH_LIMIT,
        exclude_same_evidence: bool = True,
        profile_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search Face Memory using a stored
        observation as the query.
        """

        normalized_id = (
            self._normalize_uuid(
                embedding_id,
                field_name="embedding_id",
            )
        )

        observation = (
            self.embedding_repository
            .get_active(
                normalized_id
            )
        )

        if observation is None:

            raise LookupError(
                "Face embedding was not found: "
                f"{normalized_id}"
            )

        embedding = [
            float(
                value
            )
            for value
            in observation.embedding
        ]

        return self.search_face(
            embedding,
            minimum_similarity=(
                minimum_similarity
            ),
            limit=limit,
            exclude_embedding_id=(
                observation.id
            ),
            exclude_evidence_id=(
                observation.evidence_id
                if exclude_same_evidence
                else None
            ),
            profile_only=(
                profile_only
            ),
        )

    # ==========================================================
    # Summaries
    # ==========================================================

    @staticmethod
    def _profile_summary(
        profile: FaceProfile,
    ) -> dict[str, Any]:
        """
        Serialize one profile.
        """

        return {
            "id": str(
                profile.id
            ),
            "label": (
                profile.label
            ),
            "description": (
                profile.description
            ),
            "status": (
                profile.status
            ),
            "created_at": (
                profile.created_at.isoformat()
                if profile.created_at
                else None
            ),
            "updated_at": (
                profile.updated_at.isoformat()
                if profile.updated_at
                else None
            ),
        }

    @staticmethod
    def _embedding_summary(
        embedding: FaceEmbedding,
    ) -> dict[str, Any]:
        """
        Serialize one stored face observation.
        """

        return {
            "id": str(
                embedding.id
            ),
            "profile_id": (
                str(
                    embedding.profile_id
                )
                if embedding.profile_id
                else None
            ),
            "evidence_id": str(
                embedding.evidence_id
            ),
            "case_id": str(
                embedding.case_id
            ),
            "face_id": (
                embedding.face_id
            ),
            "face_index": (
                embedding.face_index
            ),
            "recognizer": (
                embedding.recognizer
            ),
            "detector": (
                embedding.detector
            ),
            "detection_confidence": (
                embedding.detection_confidence
            ),
            "bbox": (
                FaceMemoryService
                ._decode_optional_json(
                    embedding.bbox_json
                )
            ),
            "source_metadata": (
                FaceMemoryService
                ._decode_optional_json(
                    embedding.source_metadata_json
                )
            ),
            "created_at": (
                embedding.created_at.isoformat()
                if embedding.created_at
                else None
            ),
        }

    # ==========================================================
    # Similarity classification
    # ==========================================================

    @staticmethod
    def _classify_similarity(
        similarity: float,
    ) -> str:
        """
        Provide a descriptive, non-identity
        classification for vector similarity.
        """

        if similarity >= 0.80:

            return "very_high"

        if similarity >= 0.65:

            return "high"

        if similarity >= 0.50:

            return "moderate"

        if similarity >= 0.40:

            return "low"

        return "very_low"

    # ==========================================================
    # JSON helpers
    # ==========================================================

    @staticmethod
    def _encode_optional_json(
        value: dict[str, Any] | None,
    ) -> str | None:
        """
        Encode optional structured metadata.
        """

        if value is None:

            return None

        if not isinstance(
            value,
            dict,
        ):

            raise TypeError(
                "JSON metadata must be a dictionary."
            )

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _decode_optional_json(
        value: str | None,
    ) -> dict[str, Any] | None:
        """
        Decode optional structured metadata.
        """

        if not value:

            return None

        try:

            decoded = json.loads(
                value
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ):

            return None

        if not isinstance(
            decoded,
            dict,
        ):

            return None

        return decoded

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Normalize required UUID.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must be a valid UUID."
            ) from error

    @classmethod
    def _normalize_optional_uuid(
        cls,
        value: str | UUID | None,
        *,
        field_name: str,
    ) -> UUID | None:
        """
        Normalize optional UUID.
        """

        if value is None:

            return None

        normalized_text = str(
            value
        ).strip()

        if not normalized_text:

            return None

        return cls._normalize_uuid(
            value,
            field_name=field_name,
        )

    @staticmethod
    def _normalize_similarity(
        value: float,
    ) -> float:
        """
        Validate cosine similarity threshold.
        """

        try:

            normalized = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "minimum_similarity must be numeric."
            ) from error

        if not math.isfinite(
            normalized
        ):

            raise ValueError(
                "minimum_similarity must be finite."
            )

        if not (
            -1.0
            <= normalized
            <= 1.0
        ):

            raise ValueError(
                (
                    "minimum_similarity must be "
                    "between -1.0 and 1.0."
                )
            )

        return normalized

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return Face Memory service information.
        """

        return {
            "type": (
                "face_memory_service"
            ),
            "embedding_dimension": (
                self.embedding_repository
                .EMBEDDING_DIMENSION
            ),
            "distance_metric": (
                "cosine"
            ),
            "default_minimum_similarity": (
                self.DEFAULT_MINIMUM_SIMILARITY
            ),
            "identity_assertion": False,
        }