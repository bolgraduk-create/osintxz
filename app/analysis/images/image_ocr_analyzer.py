"""
Image OCR analyzer.

Block 8 — Multimodal Analysis / OCR Integration.

Supported profiles:

default
    RapidOCR default recognition profile.

cyrillic
    PP-OCRv5 Cyrillic recognition profile for languages
    including Russian, Ukrainian, Bulgarian and English.

Architecture:

ImageAnalysisContext
        ↓
ImageOCRAnalyzer
        ↓
RapidOCR
        ↓
ONNX Runtime
        ↓
text + blocks + bounding boxes + confidence
        ↓
ImageAnalysisResult


Semantic boundaries:

OCR text
    != verified factual statement

OCR confidence
    != Evidence confidence

OCR confidence
    != source reliability

recognized name
    != Entity Resolution match


The analyzer performs no:

- database writes
- repository access
- Evidence mutation
- Entity mutation
- Relationship creation
- Entity Resolution
"""

from __future__ import annotations

import importlib.util

from math import (
    isfinite,
)

from pathlib import (
    Path,
)

from statistics import (
    fmean,
)

from threading import (
    RLock,
)

from time import (
    perf_counter,
)

from typing import (
    Any,
)

import numpy as np

from PIL import (
    Image,
)

from app.analysis.images.base_image_analyzer import (
    BaseImageAnalyzer,
)

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
    ImageAnalysisStatus,
)


# ==========================================================
# OCR profiles
# ==========================================================


OCR_PROFILE_DEFAULT = "default"

OCR_PROFILE_CYRILLIC = "cyrillic"


SUPPORTED_OCR_PROFILES: tuple[
    str,
    ...,
] = (
    OCR_PROFILE_DEFAULT,
    OCR_PROFILE_CYRILLIC,
)


# ==========================================================
# Local model files
# ==========================================================


RAPIDOCR_DETECTION_MODEL = (
    "PP-OCRv6_det_small.onnx"
)

RAPIDOCR_CLASSIFICATION_MODEL = (
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
)

RAPIDOCR_DEFAULT_RECOGNITION_MODEL = (
    "PP-OCRv6_rec_small.onnx"
)

RAPIDOCR_CYRILLIC_RECOGNITION_MODEL = (
    "cyrillic_PP-OCRv5_rec_mobile.onnx"
)


RAPIDOCR_PROFILE_MODEL_FILES: dict[
    str,
    tuple[
        str,
        ...,
    ],
] = {
    OCR_PROFILE_DEFAULT: (
        RAPIDOCR_DETECTION_MODEL,
        RAPIDOCR_CLASSIFICATION_MODEL,
        RAPIDOCR_DEFAULT_RECOGNITION_MODEL,
    ),
    OCR_PROFILE_CYRILLIC: (
        RAPIDOCR_DETECTION_MODEL,
        RAPIDOCR_CLASSIFICATION_MODEL,
        RAPIDOCR_CYRILLIC_RECOGNITION_MODEL,
    ),
}


# ==========================================================
# Analyzer
# ==========================================================


class ImageOCRAnalyzer(
    BaseImageAnalyzer
):
    """
    Extract visible text from image evidence.

    OCR engines are initialized lazily and cached per profile.
    """

    name = "ocr"

    description = (
        "Extract visible text, bounding boxes and OCR "
        "confidence from image evidence."
    )

    version = "1.1"

    # ======================================================
    # Process-local OCR engine cache
    # ======================================================

    _engines: dict[
        str,
        Any,
    ] = {}

    _engine_lock = RLock()

    _inference_lock = RLock()

    # ======================================================
    # Availability
    # ======================================================

    def is_available(
        self,
    ) -> bool:
        """
        Registry availability is based on the default profile.

        Optional profiles can independently return UNAVAILABLE
        when their local recognition model is missing.
        """

        if (
            importlib.util.find_spec(
                "rapidocr"
            )
            is None
        ):

            return False

        if (
            importlib.util.find_spec(
                "onnxruntime"
            )
            is None
        ):

            return False

        return (
            len(
                self._missing_model_files(
                    OCR_PROFILE_DEFAULT
                )
            )
            ==
            0
        )

    def unavailable_reason(
        self,
    ) -> str:

        if (
            importlib.util.find_spec(
                "rapidocr"
            )
            is None
        ):

            return (
                "The rapidocr package is not installed."
            )

        if (
            importlib.util.find_spec(
                "onnxruntime"
            )
            is None
        ):

            return (
                "ONNX Runtime is not installed."
            )

        missing = (
            self._missing_model_files(
                OCR_PROFILE_DEFAULT
            )
        )

        if missing:

            return (
                "RapidOCR default local model files "
                "are missing: "
                +
                ", ".join(
                    missing
                )
            )

        return ""

    # ======================================================
    # Analysis
    # ======================================================

    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:

        if not isinstance(
            context,
            ImageAnalysisContext,
        ):

            raise TypeError(
                "context must be ImageAnalysisContext."
            )

        # ==================================================
        # Options
        # ==================================================

        try:

            profile = (
                self._normalize_profile(
                    context.get_option(
                        "ocr_profile",
                        OCR_PROFILE_DEFAULT,
                    )
                )
            )

            use_preview = (
                self._normalize_bool(
                    context.get_option(
                        "ocr_use_preview",
                        False,
                    ),
                    option_name=(
                        "ocr_use_preview"
                    ),
                )
            )

            min_confidence = (
                self._normalize_confidence(
                    context.get_option(
                        "ocr_min_confidence",
                        0.0,
                    )
                )
            )

        except Exception as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    str(
                        error
                    )
                ],
                metadata=self.metadata(),
            )

        # ==================================================
        # Source path
        # ==================================================

        source_path = Path(
            context.analysis_path
            if use_preview
            else context.original_path
        )

        if not source_path.exists():

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "OCR source image does not exist: "
                        f"{source_path}"
                    )
                ],
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        if not source_path.is_file():

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "OCR source path is not a file: "
                        f"{source_path}"
                    )
                ],
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        # ==================================================
        # Validate image
        # ==================================================

        try:

            with Image.open(
                source_path
            ) as image:

                image.verify()

        except Exception as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "OCR image validation failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        # ==================================================
        # Local-only model boundary
        # ==================================================

        missing_models = (
            self._missing_model_files(
                profile
            )
        )

        if missing_models:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.UNAVAILABLE
                ),
                data={},
                warnings=[
                    (
                        f"RapidOCR '{profile}' profile "
                        "local model files are missing: "
                        +
                        ", ".join(
                            missing_models
                        )
                    )
                ],
                errors=[],
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        # ==================================================
        # OCR engine
        # ==================================================

        try:

            engine = (
                self._get_engine(
                    profile
                )
            )

        except Exception as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.UNAVAILABLE
                ),
                data={},
                warnings=[
                    (
                        "RapidOCR engine could not "
                        "be initialized."
                    )
                ],
                errors=[
                    (
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        # ==================================================
        # OCR inference
        # ==================================================

        started_at = (
            perf_counter()
        )

        try:

            with self._inference_lock:

                output = engine(
                    str(
                        source_path
                    )
                )

        except Exception as error:

            execution_time = (
                perf_counter()
                -
                started_at
            )

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                warnings=[],
                errors=[
                    (
                        "OCR inference failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                execution_time=(
                    execution_time
                ),
                metadata=self._result_metadata(
                    profile=profile,
                ),
            )

        execution_time = (
            perf_counter()
            -
            started_at
        )

        # ==================================================
        # Backend output
        # ==================================================

        raw_texts = getattr(
            output,
            "txts",
            None,
        )

        raw_scores = getattr(
            output,
            "scores",
            None,
        )

        raw_boxes = getattr(
            output,
            "boxes",
            None,
        )

        texts = (
            tuple(
                raw_texts
            )
            if raw_texts is not None
            else ()
        )

        scores = (
            tuple(
                raw_scores
            )
            if raw_scores is not None
            else ()
        )

        boxes = (
            tuple(
                raw_boxes
            )
            if raw_boxes is not None
            else ()
        )

        warnings: list[
            str
        ] = []

        # ==================================================
        # Normalize text blocks
        # ==================================================

        blocks: list[
            dict[
                str,
                Any,
            ]
        ] = []

        filtered_count = 0

        for index, raw_text in enumerate(
            texts
        ):

            text = str(
                raw_text
            ).strip()

            if not text:

                continue

            confidence: (
                float
                |
                None
            ) = None

            if index < len(
                scores
            ):

                try:

                    candidate = float(
                        scores[
                            index
                        ]
                    )

                    if isfinite(
                        candidate
                    ):

                        confidence = (
                            candidate
                        )

                except (
                    TypeError,
                    ValueError,
                ):

                    confidence = None

            if (
                confidence
                is not None
                and
                confidence
                <
                min_confidence
            ):

                filtered_count += 1

                continue

            box = None

            if index < len(
                boxes
            ):

                box = (
                    self._normalize_box(
                        boxes[
                            index
                        ]
                    )
                )

            blocks.append(
                {
                    "text": text,
                    "confidence": (
                        confidence
                    ),
                    "box": box,
                }
            )

        # ==================================================
        # Combined text
        # ==================================================

        combined_text = "\n".join(
            block[
                "text"
            ]
            for block
            in blocks
        )

        valid_confidences = [
            block[
                "confidence"
            ]
            for block
            in blocks
            if (
                block[
                    "confidence"
                ]
                is not None
            )
        ]

        mean_confidence = (
            float(
                fmean(
                    valid_confidences
                )
            )
            if valid_confidences
            else None
        )

        # ==================================================
        # Result warnings
        # ==================================================

        if (
            len(
                scores
            )
            !=
            len(
                texts
            )
        ):

            warnings.append(
                (
                    "RapidOCR returned a different "
                    "number of confidence scores "
                    "and text blocks."
                )
            )

        if (
            raw_boxes is not None
            and
            len(
                boxes
            )
            !=
            len(
                texts
            )
        ):

            warnings.append(
                (
                    "RapidOCR returned a different "
                    "number of bounding boxes "
                    "and text blocks."
                )
            )

        if filtered_count:

            warnings.append(
                (
                    f"{filtered_count} OCR text "
                    "block(s) were removed by "
                    "ocr_min_confidence."
                )
            )

        if not blocks:

            warnings.append(
                (
                    "OCR completed successfully, "
                    "but no visible text blocks "
                    "were retained."
                )
            )

        status = (
            ImageAnalysisStatus
            .COMPLETED_WITH_WARNINGS
            if warnings
            else
            ImageAnalysisStatus.COMPLETED
        )

        # ==================================================
        # Result
        # ==================================================

        return ImageAnalysisResult(
            analyzer=self.name,
            status=status,
            data={
                "text": combined_text,
                "blocks": blocks,
                "block_count": len(
                    blocks
                ),
                "detected_block_count": len(
                    texts
                ),
                "filtered_block_count": (
                    filtered_count
                ),
                "mean_confidence": (
                    mean_confidence
                ),
                "minimum_confidence": (
                    min_confidence
                ),
                "profile": profile,
            },
            warnings=warnings,
            errors=[],
            execution_time=(
                execution_time
            ),
            metadata={
                **self._result_metadata(
                    profile=profile,
                ),
                "source_path": str(
                    source_path
                ),
                "original_path": str(
                    context.original_path
                ),
                "analysis_uses_preview": (
                    source_path
                    !=
                    context.original_path
                ),
            },
        )

    # ======================================================
    # Local model paths
    # ======================================================

    @staticmethod
    def _rapidocr_models_dir(
    ) -> Path | None:

        spec = importlib.util.find_spec(
            "rapidocr"
        )

        if (
            spec is None
            or
            spec.submodule_search_locations
            is None
        ):

            return None

        locations = list(
            spec.submodule_search_locations
        )

        if not locations:

            return None

        return (
            Path(
                locations[
                    0
                ]
            )
            /
            "models"
        )

    @classmethod
    def _missing_model_files(
        cls,
        profile: str,
    ) -> tuple[
        str,
        ...,
    ]:

        profile = (
            cls._normalize_profile(
                profile
            )
        )

        required_files = (
            RAPIDOCR_PROFILE_MODEL_FILES[
                profile
            ]
        )

        models_dir = (
            cls._rapidocr_models_dir()
        )

        if models_dir is None:

            return tuple(
                required_files
            )

        return tuple(
            filename
            for filename
            in required_files
            if not (
                models_dir
                /
                filename
            ).is_file()
        )

    # ======================================================
    # Lazy engine
    # ======================================================

    @classmethod
    def _get_engine(
        cls,
        profile: str,
    ) -> Any:

        profile = (
            cls._normalize_profile(
                profile
            )
        )

        existing = (
            cls._engines.get(
                profile
            )
        )

        if existing is not None:

            return existing

        with cls._engine_lock:

            existing = (
                cls._engines.get(
                    profile
                )
            )

            if existing is not None:

                return existing

            missing = (
                cls._missing_model_files(
                    profile
                )
            )

            if missing:

                raise RuntimeError(
                    (
                        f"RapidOCR '{profile}' "
                        "local models are missing: "
                    )
                    +
                    ", ".join(
                        missing
                    )
                )

            from rapidocr import (
                RapidOCR,
            )

            if (
                profile
                ==
                OCR_PROFILE_DEFAULT
            ):

                engine = (
                    RapidOCR()
                )

            elif (
                profile
                ==
                OCR_PROFILE_CYRILLIC
            ):

                from rapidocr import (
                    EngineType,
                    LangRec,
                    ModelType,
                    OCRVersion,
                )

                engine = RapidOCR(
                    params={
                        "Rec.engine_type": (
                            EngineType.ONNXRUNTIME
                        ),
                        "Rec.lang_type": (
                            LangRec.CYRILLIC
                        ),
                        "Rec.model_type": (
                            ModelType.MOBILE
                        ),
                        "Rec.ocr_version": (
                            OCRVersion.PPOCRV5
                        ),
                    }
                )

            else:

                raise RuntimeError(
                    (
                        "Unsupported OCR profile: "
                        f"{profile}"
                    )
                )

            cls._engines[
                profile
            ] = engine

            return engine

    # ======================================================
    # Option normalization
    # ======================================================

    @staticmethod
    def _normalize_profile(
        value: Any,
    ) -> str:

        if not isinstance(
            value,
            str,
        ):

            raise TypeError(
                "ocr_profile must be str."
            )

        profile = (
            value
            .strip()
            .lower()
        )

        if (
            profile
            not in
            SUPPORTED_OCR_PROFILES
        ):

            raise ValueError(
                (
                    "Unsupported ocr_profile. "
                    "Expected one of: "
                )
                +
                ", ".join(
                    SUPPORTED_OCR_PROFILES
                )
                +
                "."
            )

        return profile

    @staticmethod
    def _normalize_bool(
        value: Any,
        *,
        option_name: str,
    ) -> bool:

        if not isinstance(
            value,
            bool,
        ):

            raise TypeError(
                f"{option_name} must be bool."
            )

        return value

    @staticmethod
    def _normalize_confidence(
        value: Any,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                "ocr_min_confidence must "
                "be a number."
            )

        try:

            confidence = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "ocr_min_confidence must "
                "be a number."
            ) from error

        if not isfinite(
            confidence
        ):

            raise ValueError(
                "ocr_min_confidence must "
                "be finite."
            )

        if not (
            0.0
            <=
            confidence
            <=
            1.0
        ):

            raise ValueError(
                "ocr_min_confidence must "
                "be between 0 and 1."
            )

        return confidence

    # ======================================================
    # Box normalization
    # ======================================================

    @staticmethod
    def _normalize_box(
        value: Any,
    ) -> (
        list[
            list[
                float
            ]
        ]
        |
        None
    ):

        try:

            array = np.asarray(
                value,
                dtype=np.float64,
            )

        except Exception:

            return None

        if (
            array.ndim
            !=
            2
            or
            array.shape[
                1
            ]
            !=
            2
        ):

            return None

        if not bool(
            np.all(
                np.isfinite(
                    array
                )
            )
        ):

            return None

        return [
            [
                float(
                    point[
                        0
                    ]
                ),
                float(
                    point[
                        1
                    ]
                ),
            ]
            for point
            in array
        ]

    # ======================================================
    # Metadata
    # ======================================================

    def metadata(
        self,
    ) -> dict[
        str,
        Any,
    ]:

        base_metadata = (
            super().metadata()
        )

        return {
            **base_metadata,
            "backend": "rapidocr",
            "runtime": "onnxruntime",
            "output": (
                "text_blocks_boxes_confidence"
            ),
            "default_profile": (
                OCR_PROFILE_DEFAULT
            ),
            "supported_profiles": list(
                SUPPORTED_OCR_PROFILES
            ),
            "network_required": False,
            "database_access": False,
        }

    def _result_metadata(
        self,
        *,
        profile: str,
    ) -> dict[
        str,
        Any,
    ]:

        profile_languages = {
            OCR_PROFILE_DEFAULT: (
                "rapidocr_default"
            ),
            OCR_PROFILE_CYRILLIC: (
                "cyrillic_ru_uk_bg_en"
            ),
        }

        return {
            **self.metadata(),
            "profile": profile,
            "language_profile": (
                profile_languages[
                    profile
                ]
            ),
        }