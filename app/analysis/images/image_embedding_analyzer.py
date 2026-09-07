"""
General image embedding analyzer.

Block 8 — Multimodal Analysis / Image Embeddings.

The analyzer creates a semantic visual embedding for the
entire image using a local CLIP vision model through
FastEmbed / ONNX Runtime.

Architecture:

ImageAnalysisContext
        ↓
CLIP ViT-B/32
        ↓
512-dimensional float32 vector
        ↓
explicit L2 normalization
        ↓
ImageAnalysisResult


Important semantic boundaries:

IMAGE_EMBEDDING
    != FACE_EMBEDDING

semantic image similarity
    != perceptual hash similarity

cosine similarity
    != Evidence confidence

cosine similarity
    != Entity Resolution confidence

image embedding
    != proof that two images depict
       the same object or person


The analyzer performs no:

- database writes
- repository access
- Evidence mutation
- Entity mutation
- Relationship creation
- Entity Resolution
- network access by default

Production inference defaults to local_files_only=True.
The model must therefore be provisioned in the local cache
before normal application use.
"""

from __future__ import annotations

from math import (
    isfinite,
)

from pathlib import (
    Path,
)

from threading import (
    RLock,
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
# Constants
# ==========================================================


IMAGE_EMBEDDING_MODEL_NAME = (
    "Qdrant/clip-ViT-B-32-vision"
)

IMAGE_EMBEDDING_DIMENSION = 512

DEFAULT_IMAGE_EMBEDDING_CACHE_DIR = Path(
    "storage/cache/fastembed_models"
)


# ==========================================================
# Analyzer
# ==========================================================


class ImageEmbeddingAnalyzer(
    BaseImageAnalyzer
):
    """
    Generate one semantic CLIP embedding for an image.

    The analyzer loads the model lazily. Importing this module
    therefore does not initialize ONNX Runtime or load model
    weights into memory.
    """

    name = "image_embeddings"

    # ======================================================
    # Shared process-local model cache
    # ======================================================

    _model_cache: dict[
        tuple[
            str,
            str,
            bool,
        ],
        Any,
    ] = {}

    _model_cache_lock = RLock()

    # ======================================================
    # Public API
    # ======================================================

    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:
        """
        Generate a normalized 512-D semantic image embedding.

        Supported context.options:

        image_embedding_cache_dir:
            Optional model-cache path.

        image_embedding_local_files_only:
            Whether model loading must remain offline.
            Defaults to True.
        """

        if not isinstance(
            context,
            ImageAnalysisContext,
        ):

            raise TypeError(
                "context must be ImageAnalysisContext."
            )

        # ==================================================
        # Resolve image path
        # ==================================================

        image_path = Path(
            context.image_path
        )

        if not image_path.exists():

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image file does not exist: "
                        f"{image_path}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        if not image_path.is_file():

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image path is not a file: "
                        f"{image_path}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Validate actual image
        # ==================================================

        try:

            with Image.open(
                image_path
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
                        "Image validation failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Runtime options
        # ==================================================

        try:

            cache_dir = (
                self._resolve_cache_dir(
                    context
                )
            )

            local_files_only = (
                self._resolve_local_files_only(
                    context
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
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Load local model
        # ==================================================

        try:

            model = self._get_model(
                cache_dir=cache_dir,
                local_files_only=(
                    local_files_only
                ),
            )

        except ImportError as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.UNAVAILABLE
                ),
                data={},
                errors=[
                    str(
                        error
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                    "backend": "fastembed",
                    "local_files_only": (
                        local_files_only
                    ),
                    "cache_dir": str(
                        cache_dir
                    ),
                },
            )

        except Exception as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.UNAVAILABLE
                ),
                data={},
                errors=[
                    (
                        "Image embedding model could not "
                        "be loaded: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                    "backend": "fastembed",
                    "local_files_only": (
                        local_files_only
                    ),
                    "cache_dir": str(
                        cache_dir
                    ),
                },
            )

        # ==================================================
        # Inference
        # ==================================================

        try:

            embeddings = list(
                model.embed(
                    (
                        image_path,
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
                    (
                        "Image embedding inference failed: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                    "backend": "fastembed",
                    "local_files_only": (
                        local_files_only
                    ),
                    "cache_dir": str(
                        cache_dir
                    ),
                },
            )

        # ==================================================
        # Cardinality contract
        # ==================================================

        if len(
            embeddings
        ) != 1:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image embedding backend returned "
                        "an unexpected number of vectors: "
                        f"{len(embeddings)}."
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                    "backend": "fastembed",
                },
            )

        # ==================================================
        # Convert to canonical float32 vector
        # ==================================================

        try:

            raw_embedding = np.asarray(
                embeddings[
                    0
                ],
                dtype=np.float32,
            ).reshape(
                -1
            )

        except Exception as error:

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image embedding could not be "
                        "converted to float32: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Dimension contract
        # ==================================================

        if (
            raw_embedding.shape
            !=
            (
                IMAGE_EMBEDDING_DIMENSION,
            )
        ):

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Unexpected image embedding "
                        "dimension: "
                        f"{raw_embedding.shape}. "
                        "Expected "
                        f"{IMAGE_EMBEDDING_DIMENSION}."
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Finite-value contract
        # ==================================================

        if not bool(
            np.all(
                np.isfinite(
                    raw_embedding
                )
            )
        ):

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image embedding contains "
                        "NaN or infinite values."
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Explicit L2 normalization
        # ==================================================

        raw_norm = float(
            np.linalg.norm(
                raw_embedding
            )
        )

        if (
            not isfinite(
                raw_norm
            )
            or
            raw_norm <= 0.0
        ):

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image embedding has an invalid "
                        f"L2 norm: {raw_norm}."
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        normalized_embedding = (
            raw_embedding
            /
            raw_norm
        ).astype(
            np.float32,
            copy=False,
        )

        normalized_norm = float(
            np.linalg.norm(
                normalized_embedding
            )
        )

        if (
            not isfinite(
                normalized_norm
            )
            or
            not np.isclose(
                normalized_norm,
                1.0,
                rtol=1e-5,
                atol=1e-6,
            )
        ):

            return ImageAnalysisResult(
                analyzer=self.name,
                status=(
                    ImageAnalysisStatus.FAILED
                ),
                data={},
                errors=[
                    (
                        "Image embedding L2 "
                        "normalization failed."
                    )
                ],
                metadata={
                    "model": (
                        IMAGE_EMBEDDING_MODEL_NAME
                    ),
                    "dimension": (
                        IMAGE_EMBEDDING_DIMENSION
                    ),
                },
            )

        # ==================================================
        # Canonical serialization
        # ==================================================

        vector = [
            float(
                value
            )
            for value
            in normalized_embedding.tolist()
        ]

        # ==================================================
        # Final result
        # ==================================================

        return ImageAnalysisResult(
            analyzer=self.name,
            status=(
                ImageAnalysisStatus.COMPLETED
            ),
            data={
                "embedding": vector,
                "dimension": (
                    IMAGE_EMBEDDING_DIMENSION
                ),
                "model": (
                    IMAGE_EMBEDDING_MODEL_NAME
                ),
                "dtype": "float32",
                "normalized": True,
                "normalization": "l2",
                "raw_norm": raw_norm,
                "normalized_norm": (
                    normalized_norm
                ),
            },
            warnings=[],
            errors=[],
            metadata={
                "backend": "fastembed",
                "runtime": "onnxruntime",
                "model": (
                    IMAGE_EMBEDDING_MODEL_NAME
                ),
                "dimension": (
                    IMAGE_EMBEDDING_DIMENSION
                ),
                "local_files_only": (
                    local_files_only
                ),
                "cache_dir": str(
                    cache_dir
                ),
                "semantic_scope": (
                    "whole_image"
                ),
            },
        )

    # ======================================================
    # Runtime options
    # ======================================================

    @staticmethod
    def _resolve_cache_dir(
        context: ImageAnalysisContext,
    ) -> Path:

        value = context.options.get(
            "image_embedding_cache_dir",
            DEFAULT_IMAGE_EMBEDDING_CACHE_DIR,
        )

        if isinstance(
            value,
            Path,
        ):

            cache_dir = value

        elif isinstance(
            value,
            str,
        ):

            normalized = value.strip()

            if not normalized:

                raise ValueError(
                    "image_embedding_cache_dir "
                    "cannot be empty."
                )

            cache_dir = Path(
                normalized
            )

        else:

            raise TypeError(
                "image_embedding_cache_dir must "
                "be str or pathlib.Path."
            )

        return cache_dir

    @staticmethod
    def _resolve_local_files_only(
        context: ImageAnalysisContext,
    ) -> bool:

        value = context.options.get(
            "image_embedding_local_files_only",
            True,
        )

        if not isinstance(
            value,
            bool,
        ):

            raise TypeError(
                "image_embedding_local_files_only "
                "must be bool."
            )

        return value

    # ======================================================
    # Lazy backend
    # ======================================================

    @classmethod
    def _get_model(
        cls,
        *,
        cache_dir: Path,
        local_files_only: bool,
    ) -> Any:
        """
        Return one process-local FastEmbed model instance.

        The model is cached by:
        - model name
        - cache directory
        - local_files_only mode
        """

        try:

            from fastembed import (
                ImageEmbedding,
            )

        except Exception as error:

            raise ImportError(
                "FastEmbed image runtime is unavailable. "
                "Install the approved fastembed runtime."
            ) from error

        cache_key = (
            IMAGE_EMBEDDING_MODEL_NAME,
            str(
                cache_dir.resolve()
            ),
            local_files_only,
        )

        with cls._model_cache_lock:

            existing = (
                cls
                ._model_cache
                .get(
                    cache_key
                )
            )

            if existing is not None:

                return existing

            model = ImageEmbedding(
                model_name=(
                    IMAGE_EMBEDDING_MODEL_NAME
                ),
                cache_dir=str(
                    cache_dir
                ),
                local_files_only=(
                    local_files_only
                ),
            )

            # Runtime dimension validation.
            if hasattr(
                model,
                "embedding_size",
            ):

                runtime_dimension = (
                    model.embedding_size
                )

                if callable(
                    runtime_dimension
                ):

                    runtime_dimension = (
                        runtime_dimension()
                    )

                if (
                    int(
                        runtime_dimension
                    )
                    !=
                    IMAGE_EMBEDDING_DIMENSION
                ):

                    raise RuntimeError(
                        "Image embedding model reports "
                        "unexpected dimension: "
                        f"{runtime_dimension}."
                    )

            cls._model_cache[
                cache_key
            ] = model

            return model