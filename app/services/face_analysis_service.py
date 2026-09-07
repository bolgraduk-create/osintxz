"""
Face analysis orchestration service.

Coordinates the complete local face-analysis pipeline:

IMAGE evidence
    ↓
YuNet face detection
    ↓
SFace embedding generation
    ↓
Persistent Face Memory observations

Responsibilities:

- run face detection
- run face embedding generation
- persist generated embeddings
- avoid duplicate observations
- return one unified application-level result

Does NOT:

- commit or rollback transactions
- assign real-world identity automatically
- search the internet
- manage UI widgets
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.face_memory_service import (
    FaceMemoryService,
)

from app.services.image_analysis_service import (
    ImageAnalysisService,
)


class FaceAnalysisService:
    """
    Orchestrates detection, embedding generation,
    and persistence into Face Memory.
    """

    def __init__(
        self,
        image_analysis_service: ImageAnalysisService,
        face_memory_service: FaceMemoryService,
    ) -> None:

        self.image_analysis_service = (
            image_analysis_service
        )

        self.face_memory_service = (
            face_memory_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze_and_remember(
        self,
        evidence_id: str | UUID,
        *,
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> dict[str, Any]:
        """
        Detect faces, generate SFace embeddings,
        and persist observations into Face Memory.

        Existing evidence/face observations are reused.
        """

        detection_result = (
            self.image_analysis_service
            .detect_faces(
                evidence_id=evidence_id,
                score_threshold=(
                    score_threshold
                ),
                nms_threshold=(
                    nms_threshold
                ),
                top_k=(
                    top_k
                ),
            )
        )

        embedding_result = (
            self.image_analysis_service
            .generate_face_embeddings(
                evidence_id=evidence_id,
            )
        )

        evidence_id_value = (
            embedding_result.get(
                "evidence_id"
            )
            or detection_result.get(
                "evidence_id"
            )
        )

        case_id_value = (
            embedding_result.get(
                "case_id"
            )
            or detection_result.get(
                "case_id"
            )
        )

        if not evidence_id_value:

            raise RuntimeError(
                "Face analysis result does not contain "
                "evidence_id."
            )

        if not case_id_value:

            raise RuntimeError(
                "Face analysis result does not contain "
                "case_id."
            )

        analysis_result = (
            embedding_result.get(
                "result",
                {},
            )
        )

        if not isinstance(
            analysis_result,
            dict,
        ):

            analysis_result = {}

        data = analysis_result.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):

            data = {}

        embeddings = data.get(
            "embeddings",
            [],
        )

        if not isinstance(
            embeddings,
            list,
        ):

            embeddings = []

        remembered: list[
            dict[str, Any]
        ] = []

        skipped: list[
            dict[str, Any]
        ] = []

        for item in embeddings:

            if not isinstance(
                item,
                dict,
            ):

                continue

            face_id = str(
                item.get(
                    "face_id"
                )
                or ""
            ).strip()

            embedding = item.get(
                "embedding"
            )

            if not face_id:

                skipped.append(
                    {
                        "reason": (
                            "missing_face_id"
                        ),
                    }
                )

                continue

            if not isinstance(
                embedding,
                list,
            ):

                skipped.append(
                    {
                        "face_id": face_id,
                        "reason": (
                            "missing_embedding"
                        ),
                    }
                )

                continue

            try:

                observation = (
                    self.face_memory_service
                    .remember_face(
                        evidence_id=(
                            evidence_id_value
                        ),
                        case_id=(
                            case_id_value
                        ),
                        face_id=face_id,
                        face_index=int(
                            item.get(
                                "face_index",
                                0,
                            )
                            or 0
                        ),
                        embedding=embedding,
                        recognizer=str(
                            item.get(
                                "recognizer"
                            )
                            or "sface"
                        ),
                        detector=str(
                            item.get(
                                "detector"
                            )
                            or "yunet"
                        ),
                        detection_confidence=(
                            item.get(
                                "detection_confidence"
                            )
                        ),
                        bbox=(
                            item.get(
                                "bbox"
                            )
                            if isinstance(
                                item.get(
                                    "bbox"
                                ),
                                dict,
                            )
                            else None
                        ),
                        source_metadata={
                            "source": (
                                "face_analysis_service"
                            ),
                            "embedding_dimension": (
                                item.get(
                                    "dimension"
                                )
                            ),
                            "normalized": (
                                item.get(
                                    "normalized"
                                )
                            ),
                        },
                    )
                )

                remembered.append(
                    observation
                )

            except Exception as exc:

                skipped.append(
                    {
                        "face_id": face_id,
                        "reason": str(
                            exc
                        ),
                    }
                )

        detection_analysis = (
            detection_result.get(
                "result",
                {},
            )
        )

        if not isinstance(
            detection_analysis,
            dict,
        ):

            detection_analysis = {}

        detection_data = (
            detection_analysis.get(
                "data",
                {},
            )
        )

        if not isinstance(
            detection_data,
            dict,
        ):

            detection_data = {}

        detected_count = int(
            detection_data.get(
                "count",
                0,
            )
            or 0
        )

        generated_count = int(
            data.get(
                "count",
                len(
                    embeddings
                ),
            )
            or 0
        )

        return {
            "evidence_id": str(
                evidence_id_value
            ),
            "case_id": str(
                case_id_value
            ),
            "detected_count": (
                detected_count
            ),
            "embedding_count": (
                generated_count
            ),
            "remembered_count": len(
                remembered
            ),
            "skipped_count": len(
                skipped
            ),
            "remembered": (
                remembered
            ),
            "skipped": (
                skipped
            ),
            "detection": (
                detection_result
            ),
            "embeddings": (
                embedding_result
            ),
        }

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return service information.
        """

        return {
            "type": (
                "face_analysis_service"
            ),
            "detector": (
                "yunet"
            ),
            "recognizer": (
                "sface"
            ),
            "embedding_dimension": (
                128
            ),
            "persistent_memory": (
                True
            ),
            "identity_assertion": (
                False
            ),
        }