"""
Face embedding analyzer.

Generates numerical face descriptors
for faces previously detected by YuNet.

Architecture:

ImageAnalysisContext
        ↓
Stored YuNet detections
        ↓
SFace alignment
        ↓
SFace feature extraction
        ↓
Face embeddings
        ↓
ImageAnalysisResult

Responsibilities:

- read previously detected face regions
- reconstruct YuNet face rows
- align detected faces
- generate SFace embeddings
- return embeddings associated with face IDs

Does NOT:

- identify people
- assign names
- search Face Memory
- access the database directly
- modify original evidence
- commit transactions
"""

from __future__ import annotations

import importlib.util

from pathlib import Path
from typing import Any

from app.analysis.images.base_image_analyzer import (
    BaseImageAnalyzer,
)

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
)


class FaceEmbeddingAnalyzer(
    BaseImageAnalyzer,
):
    """
    Generate SFace embeddings for detected faces.
    """

    name = "face_embeddings"

    description = (
        "Generate numerical SFace descriptors "
        "for previously detected faces."
    )

    version = "1.0"

    DEFAULT_MODEL_PATH = (
        Path(
            "storage"
        )
        / "models"
        / "face_recognition"
        / "face_recognition_sface_2021dec.onnx"
    )

    # ==========================================================
    # Availability
    # ==========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether SFace can be used.
        """

        if (
            importlib.util.find_spec(
                "cv2"
            )
            is None
        ):

            return False

        try:

            import cv2

        except ImportError:

            return False

        if not hasattr(
            cv2,
            "FaceRecognizerSF",
        ):

            return False

        return (
            self.DEFAULT_MODEL_PATH.is_file()
        )

    def unavailable_reason(
        self,
    ) -> str:
        """
        Explain why SFace is unavailable.
        """

        if (
            importlib.util.find_spec(
                "cv2"
            )
            is None
        ):

            return (
                "OpenCV is not installed. "
                "Install it with: "
                "python -m pip install opencv-python"
            )

        if not self.DEFAULT_MODEL_PATH.is_file():

            return (
                "SFace model is missing: "
                f"{self.DEFAULT_MODEL_PATH}"
            )

        return (
            "The installed OpenCV build does not "
            "provide FaceRecognizerSF."
        )

    # ==========================================================
    # Analysis
    # ==========================================================

    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:
        """
        Generate an embedding for every detected face.
        """

        import cv2
        import numpy as np

        analysis_path = (
            context.analysis_path
        )

        model_path = (
            self._resolve_model_path(
                context.get_option(
                    "model_path",
                    None,
                )
            )
        )

        detected_faces = (
            self._extract_detected_faces(
                context.metadata
            )
        )

        if not detected_faces:

            return (
                ImageAnalysisResult
                .skipped(
                    analyzer=self.name,
                    reason=(
                        "No stored YuNet face detections "
                        "are available. Run face detection "
                        "before generating embeddings."
                    ),
                    metadata=self.metadata(),
                )
            )

        image = cv2.imread(
            str(
                analysis_path
            )
        )

        if image is None:

            raise ValueError(
                "OpenCV could not read the image: "
                f"{analysis_path}"
            )

        recognizer = (
            cv2.FaceRecognizerSF.create(
                str(
                    model_path
                ),
                "",
            )
        )

        embeddings: list[
            dict[str, Any]
        ] = []

        warnings: list[str] = []

        for face in detected_faces:

            face_id = str(
                face.get(
                    "id"
                )
                or ""
            ).strip()

            if not face_id:

                face_id = (
                    f"face_{len(embeddings) + 1}"
                )

            try:

                face_row = (
                    self._build_yunet_face_row(
                        face
                    )
                )

                aligned_face = (
                    recognizer.alignCrop(
                        image,
                        face_row,
                    )
                )

                if aligned_face is None:

                    raise RuntimeError(
                        "SFace alignment returned no image."
                    )

                feature = (
                    recognizer.feature(
                        aligned_face
                    )
                )

                if feature is None:

                    raise RuntimeError(
                        "SFace feature extraction "
                        "returned no vector."
                    )

                embedding_array = np.asarray(
                    feature,
                    dtype=np.float32,
                ).reshape(
                    -1
                )

                if embedding_array.size <= 0:

                    raise RuntimeError(
                        "SFace returned an empty embedding."
                    )

                if not np.all(
                    np.isfinite(
                        embedding_array
                    )
                ):

                    raise RuntimeError(
                        "SFace returned non-finite "
                        "embedding values."
                    )

                normalized_embedding = (
                    self._l2_normalize(
                        embedding_array
                    )
                )

                embeddings.append(
                    {
                        "face_id": face_id,
                        "face_index": int(
                            face.get(
                                "index",
                                len(
                                    embeddings
                                ),
                            )
                            or 0
                        ),
                        "embedding": [
                            float(
                                value
                            )
                            for value
                            in normalized_embedding
                        ],
                        "dimension": int(
                            normalized_embedding.size
                        ),
                        "normalized": True,
                        "recognizer": "sface",
                        "model": (
                            model_path.name
                        ),
                        "detector": str(
                            face.get(
                                "detector"
                            )
                            or "yunet"
                        ),
                        "detection_confidence": (
                            self._optional_float(
                                face.get(
                                    "confidence"
                                )
                            )
                        ),
                        "bbox": dict(
                            face.get(
                                "bbox",
                                {},
                            )
                            if isinstance(
                                face.get(
                                    "bbox"
                                ),
                                dict,
                            )
                            else {}
                        ),
                    }
                )

            except Exception as error:

                warnings.append(
                    (
                        f"{face_id}: embedding "
                        f"generation failed: {error}"
                    )
                )

        if not embeddings:

            return (
                ImageAnalysisResult
                .completed(
                    analyzer=self.name,
                    data={
                        "embeddings": [],
                        "count": 0,
                        "source_face_count": len(
                            detected_faces
                        ),
                        "recognizer": {
                            "name": "sface",
                            "model": str(
                                model_path
                            ),
                        },
                    },
                    warnings=warnings,
                    metadata=self.metadata(),
                )
            )

        dimensions = sorted(
            {
                int(
                    item[
                        "dimension"
                    ]
                )
                for item
                in embeddings
            }
        )

        return (
            ImageAnalysisResult
            .completed(
                analyzer=self.name,
                data={
                    "embeddings": embeddings,
                    "count": len(
                        embeddings
                    ),
                    "source_face_count": len(
                        detected_faces
                    ),
                    "dimensions": dimensions,
                    "recognizer": {
                        "name": "sface",
                        "model": str(
                            model_path
                        ),
                        "normalized": True,
                    },
                    "analysis_path": str(
                        analysis_path
                    ),
                    "original_path": str(
                        context.original_path
                    ),
                    "analysis_uses_preview": (
                        analysis_path
                        != context.original_path
                    ),
                },
                warnings=warnings,
                metadata=self.metadata(),
            )
        )

    # ==========================================================
    # Face metadata
    # ==========================================================

    @staticmethod
    def _extract_detected_faces(
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Read previously saved YuNet detections.

        Expected metadata structure:

        image_analysis
            -> faces
                -> data
                    -> faces
        """

        image_analysis = metadata.get(
            "image_analysis"
        )

        if not isinstance(
            image_analysis,
            dict,
        ):

            return []

        face_result = (
            image_analysis.get(
                "faces"
            )
        )

        if not isinstance(
            face_result,
            dict,
        ):

            return []

        data = face_result.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):

            return []

        raw_faces = data.get(
            "faces"
        )

        if not isinstance(
            raw_faces,
            list,
        ):

            return []

        return [
            face
            for face
            in raw_faces
            if isinstance(
                face,
                dict,
            )
        ]

    # ==========================================================
    # YuNet reconstruction
    # ==========================================================

    @staticmethod
    def _build_yunet_face_row(
        face: dict[str, Any],
    ) -> Any:
        """
        Reconstruct the YuNet 15-value face row
        required by FaceRecognizerSF.alignCrop().
        """

        import numpy as np

        bbox = face.get(
            "bbox"
        )

        landmarks = face.get(
            "landmarks"
        )

        if not isinstance(
            bbox,
            dict,
        ):

            raise ValueError(
                "Face detection does not contain bbox."
            )

        if not isinstance(
            landmarks,
            dict,
        ):

            raise ValueError(
                "Face detection does not contain landmarks."
            )

        right_eye = (
            FaceEmbeddingAnalyzer
            ._require_point(
                landmarks,
                "right_eye",
            )
        )

        left_eye = (
            FaceEmbeddingAnalyzer
            ._require_point(
                landmarks,
                "left_eye",
            )
        )

        nose = (
            FaceEmbeddingAnalyzer
            ._require_point(
                landmarks,
                "nose",
            )
        )

        right_mouth = (
            FaceEmbeddingAnalyzer
            ._require_point(
                landmarks,
                "right_mouth_corner",
            )
        )

        left_mouth = (
            FaceEmbeddingAnalyzer
            ._require_point(
                landmarks,
                "left_mouth_corner",
            )
        )

        confidence = float(
            face.get(
                "confidence",
                1.0,
            )
            or 1.0
        )

        values = [
            float(
                bbox.get(
                    "x",
                    0.0,
                )
            ),
            float(
                bbox.get(
                    "y",
                    0.0,
                )
            ),
            float(
                bbox.get(
                    "width",
                    0.0,
                )
            ),
            float(
                bbox.get(
                    "height",
                    0.0,
                )
            ),
            right_eye[
                0
            ],
            right_eye[
                1
            ],
            left_eye[
                0
            ],
            left_eye[
                1
            ],
            nose[
                0
            ],
            nose[
                1
            ],
            right_mouth[
                0
            ],
            right_mouth[
                1
            ],
            left_mouth[
                0
            ],
            left_mouth[
                1
            ],
            confidence,
        ]

        return np.asarray(
            values,
            dtype=np.float32,
        )

    @staticmethod
    def _require_point(
        landmarks: dict[str, Any],
        name: str,
    ) -> tuple[float, float]:
        """
        Read one required facial landmark.
        """

        point = landmarks.get(
            name
        )

        if not isinstance(
            point,
            dict,
        ):

            raise ValueError(
                f"Missing face landmark: {name}"
            )

        try:

            x = float(
                point[
                    "x"
                ]
            )

            y = float(
                point[
                    "y"
                ]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"Invalid face landmark: {name}"
            ) from error

        return (
            x,
            y,
        )

    # ==========================================================
    # Embedding helpers
    # ==========================================================

    @staticmethod
    def _l2_normalize(
        embedding: Any,
    ) -> Any:
        """
        L2-normalize an embedding vector.
        """

        import numpy as np

        vector = np.asarray(
            embedding,
            dtype=np.float32,
        ).reshape(
            -1
        )

        norm = float(
            np.linalg.norm(
                vector
            )
        )

        if norm <= 0.0:

            raise ValueError(
                "Face embedding has zero norm."
            )

        return (
            vector
            / norm
        )

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:

        if value is None:

            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    # ==========================================================
    # Model
    # ==========================================================

    @classmethod
    def _resolve_model_path(
        cls,
        value: Any,
    ) -> Path:
        """
        Resolve SFace model path.
        """

        if value is None:

            path = (
                cls.DEFAULT_MODEL_PATH
            )

        else:

            path = Path(
                str(
                    value
                )
            ).expanduser()

        try:

            path = path.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                "SFace model does not exist: "
                f"{path}"
            ) from error

        if not path.is_file():

            raise ValueError(
                "SFace model path is not a file: "
                f"{path}"
            )

        return path

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return analyzer information.
        """

        base_metadata = (
            super().metadata()
        )

        return {
            **base_metadata,
            "recognizer": "sface",
            "model": str(
                self.DEFAULT_MODEL_PATH
            ),
            "requires_analyzer": "faces",
            "embedding_normalization": "l2",
            "identity_assignment": False,
        }