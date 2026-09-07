"""
Image face analyzer.

Detects face regions in image evidence
using the YuNet neural network.

Architecture:

ImageAnalysisContext
        ↓
ImageFaceAnalyzer
        ↓
YuNet
        ↓
Face bounding boxes
        ↓
Facial landmarks
        ↓
Detection confidence
        ↓
ImageAnalysisResult

Responsibilities:

- load a pixel-compatible image
- run YuNet face detection
- return bounding boxes
- return five facial landmarks
- return confidence scores
- preserve original evidence files

Does NOT:

- identify people
- assign identities
- compare faces
- generate face embeddings
- access the database
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


class ImageFaceAnalyzer(
    BaseImageAnalyzer,
):
    """
    Detect face regions with YuNet.
    """

    name = "faces"

    description = (
        "Detect face regions and facial landmarks "
        "using the YuNet neural network."
    )

    version = "2.0"

    DEFAULT_SCORE_THRESHOLD = 0.6

    DEFAULT_NMS_THRESHOLD = 0.3

    DEFAULT_TOP_K = 5000

    DEFAULT_MODEL_PATH = (
        Path(
            "storage"
        )
        / "models"
        / "face_detection"
        / "face_detection_yunet_2023mar.onnx"
    )

    # ==========================================================
    # Availability
    # ==========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether OpenCV and YuNet are available.
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
            "FaceDetectorYN",
        ):

            return False

        return (
            self.DEFAULT_MODEL_PATH.is_file()
        )

    def unavailable_reason(
        self,
    ) -> str:
        """
        Explain why the analyzer is unavailable.
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
                "YuNet model is missing: "
                f"{self.DEFAULT_MODEL_PATH}"
            )

        return (
            "The installed OpenCV build does not "
            "provide FaceDetectorYN."
        )

    # ==========================================================
    # Analysis
    # ==========================================================

    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:
        """
        Detect faces with YuNet.
        """

        import cv2

        analysis_path = (
            context.analysis_path
        )

        score_threshold = (
            self._normalize_score_threshold(
                context.get_option(
                    "score_threshold",
                    self.DEFAULT_SCORE_THRESHOLD,
                )
            )
        )

        nms_threshold = (
            self._normalize_nms_threshold(
                context.get_option(
                    "nms_threshold",
                    self.DEFAULT_NMS_THRESHOLD,
                )
            )
        )

        top_k = (
            self._normalize_top_k(
                context.get_option(
                    "top_k",
                    self.DEFAULT_TOP_K,
                )
            )
        )

        model_path = (
            self._resolve_model_path(
                context.get_option(
                    "model_path",
                    None,
                )
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

        image_height, image_width = (
            image.shape[:2]
        )

        if (
            image_width <= 0
            or image_height <= 0
        ):

            raise ValueError(
                "The analysis image has invalid dimensions."
            )

        detector = (
            cv2.FaceDetectorYN.create(
                str(
                    model_path
                ),
                "",
                (
                    image_width,
                    image_height,
                ),
                score_threshold,
                nms_threshold,
                top_k,
            )
        )

        detector.setInputSize(
            (
                image_width,
                image_height,
            )
        )

        (
            _,
            detections,
        ) = detector.detect(
            image
        )

        faces: list[
            dict[str, Any]
        ] = []

        if detections is not None:

            for index, row in enumerate(
                detections,
                start=1,
            ):

                face = (
                    self._parse_detection(
                        row=row,
                        index=index,
                        image_width=image_width,
                        image_height=image_height,
                    )
                )

                if face is not None:

                    faces.append(
                        face
                    )

        faces.sort(
            key=lambda item: (
                float(
                    item.get(
                        "confidence",
                        0.0,
                    )
                )
            ),
            reverse=True,
        )

        for index, face in enumerate(
            faces,
            start=1,
        ):

            face[
                "id"
            ] = (
                f"face_{index}"
            )

            face[
                "index"
            ] = (
                index - 1
            )

        warnings: list[str] = []

        if not faces:

            warnings.append(
                (
                    "No face regions were detected "
                    "by YuNet."
                )
            )

        data = {
            "faces": faces,
            "count": len(
                faces
            ),
            "image": {
                "width": image_width,
                "height": image_height,
            },
            "detector": {
                "name": "yunet",
                "model": str(
                    model_path
                ),
                "score_threshold": (
                    score_threshold
                ),
                "nms_threshold": (
                    nms_threshold
                ),
                "top_k": (
                    top_k
                ),
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
        }

        return (
            ImageAnalysisResult
            .completed(
                analyzer=self.name,
                data=data,
                warnings=warnings,
                metadata=self.metadata(),
            )
        )

    # ==========================================================
    # Detection parsing
    # ==========================================================

    @staticmethod
    def _parse_detection(
        *,
        row: Any,
        index: int,
        image_width: int,
        image_height: int,
    ) -> dict[str, Any] | None:
        """
        Convert one YuNet detection row
        to the application's face structure.

        YuNet layout:

        0: x
        1: y
        2: width
        3: height

        4-5:
            right eye

        6-7:
            left eye

        8-9:
            nose tip

        10-11:
            right mouth corner

        12-13:
            left mouth corner

        14:
            confidence
        """

        if (
            row is None
            or len(
                row
            ) < 15
        ):

            return None

        x = int(
            round(
                float(
                    row[
                        0
                    ]
                )
            )
        )

        y = int(
            round(
                float(
                    row[
                        1
                    ]
                )
            )
        )

        width = int(
            round(
                float(
                    row[
                        2
                    ]
                )
            )
        )

        height = int(
            round(
                float(
                    row[
                        3
                    ]
                )
            )
        )

        x = max(
            0,
            min(
                x,
                image_width - 1,
            ),
        )

        y = max(
            0,
            min(
                y,
                image_height - 1,
            ),
        )

        width = max(
            1,
            min(
                width,
                image_width - x,
            ),
        )

        height = max(
            1,
            min(
                height,
                image_height - y,
            ),
        )

        confidence = float(
            row[
                14
            ]
        )

        right = (
            x + width
        )

        bottom = (
            y + height
        )

        center_x = (
            x
            + width / 2.0
        )

        center_y = (
            y
            + height / 2.0
        )

        area = (
            width
            * height
        )

        image_area = (
            image_width
            * image_height
        )

        landmarks = {
            "right_eye": {
                "x": float(
                    row[
                        4
                    ]
                ),
                "y": float(
                    row[
                        5
                    ]
                ),
            },
            "left_eye": {
                "x": float(
                    row[
                        6
                    ]
                ),
                "y": float(
                    row[
                        7
                    ]
                ),
            },
            "nose": {
                "x": float(
                    row[
                        8
                    ]
                ),
                "y": float(
                    row[
                        9
                    ]
                ),
            },
            "right_mouth_corner": {
                "x": float(
                    row[
                        10
                    ]
                ),
                "y": float(
                    row[
                        11
                    ]
                ),
            },
            "left_mouth_corner": {
                "x": float(
                    row[
                        12
                    ]
                ),
                "y": float(
                    row[
                        13
                    ]
                ),
            },
        }

        normalized_landmarks = {
            key: {
                "x": round(
                    (
                        value[
                            "x"
                        ]
                        / image_width
                    ),
                    6,
                ),
                "y": round(
                    (
                        value[
                            "y"
                        ]
                        / image_height
                    ),
                    6,
                ),
            }
            for key, value
            in landmarks.items()
        }

        return {
            "id": (
                f"face_{index}"
            ),
            "index": (
                index - 1
            ),
            "confidence": round(
                confidence,
                6,
            ),
            "bbox": {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "right": right,
                "bottom": bottom,
            },
            "normalized_bbox": {
                "x": round(
                    x / image_width,
                    6,
                ),
                "y": round(
                    y / image_height,
                    6,
                ),
                "width": round(
                    width / image_width,
                    6,
                ),
                "height": round(
                    height / image_height,
                    6,
                ),
            },
            "center": {
                "x": round(
                    center_x,
                    3,
                ),
                "y": round(
                    center_y,
                    3,
                ),
            },
            "normalized_center": {
                "x": round(
                    center_x
                    / image_width,
                    6,
                ),
                "y": round(
                    center_y
                    / image_height,
                    6,
                ),
            },
            "area": area,
            "relative_area": round(
                (
                    area
                    / image_area
                    if image_area > 0
                    else 0.0
                ),
                6,
            ),
            "landmarks": (
                landmarks
            ),
            "normalized_landmarks": (
                normalized_landmarks
            ),
            "detector": (
                "yunet"
            ),
        }

    # ==========================================================
    # Model
    # ==========================================================

    @classmethod
    def _resolve_model_path(
        cls,
        value: Any,
    ) -> Path:
        """
        Resolve YuNet model path.
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

            path = (
                path.resolve(
                    strict=True
                )
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                "YuNet model does not exist: "
                f"{path}"
            ) from error

        if not path.is_file():

            raise ValueError(
                "YuNet model path is not a file: "
                f"{path}"
            )

        return path

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_score_threshold(
        value: Any,
    ) -> float:

        try:

            normalized = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "score_threshold must be numeric."
            ) from error

        if not (
            0.0
            < normalized
            <= 1.0
        ):

            raise ValueError(
                "score_threshold must be "
                "between 0 and 1."
            )

        return normalized

    @staticmethod
    def _normalize_nms_threshold(
        value: Any,
    ) -> float:

        try:

            normalized = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "nms_threshold must be numeric."
            ) from error

        if not (
            0.0
            <= normalized
            <= 1.0
        ):

            raise ValueError(
                "nms_threshold must be "
                "between 0 and 1."
            )

        return normalized

    @staticmethod
    def _normalize_top_k(
        value: Any,
    ) -> int:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                "top_k must be an integer."
            )

        try:

            normalized = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "top_k must be an integer."
            ) from error

        if normalized <= 0:

            raise ValueError(
                "top_k must be greater than zero."
            )

        if normalized > 100000:

            raise ValueError(
                "top_k is unreasonably large."
            )

        return normalized

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
            "detector": "yunet",
            "model": str(
                self.DEFAULT_MODEL_PATH
            ),
            "landmark_count": 5,
            "default_score_threshold": (
                self.DEFAULT_SCORE_THRESHOLD
            ),
            "default_nms_threshold": (
                self.DEFAULT_NMS_THRESHOLD
            ),
            "default_top_k": (
                self.DEFAULT_TOP_K
            ),
            "identity_recognition": False,
        }