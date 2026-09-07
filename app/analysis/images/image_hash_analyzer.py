"""
Image hash analyzer.

Calculates cryptographic and perceptual hashes
for image evidence.

Cryptographic hashes are calculated from the original
unmodified evidence file:

- MD5
- SHA-1
- SHA-256
- SHA-512

Perceptual hashes are calculated from the best
pixel-compatible analysis path:

- average hash (aHash)
- difference hash (dHash)
- perceptual hash (pHash)
- wavelet hash (wHash)
- color hash

Responsible for:

- streaming cryptographic hash calculation
- opening a normalized image through Pillow
- calculating perceptual image fingerprints
- returning a unified ImageAnalysisResult
- preserving the original evidence file

Does NOT:

- access the database
- modify images
- compare separate images
- search the evidence collection
- commit transactions
"""

from __future__ import annotations

import hashlib
import importlib.util

from pathlib import Path
from typing import Any

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)

from app.analysis.images.base_image_analyzer import (
    BaseImageAnalyzer,
)

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
)


class ImageHashAnalyzer(
    BaseImageAnalyzer,
):
    """
    Calculate cryptographic and perceptual image hashes.
    """

    name = "hashes"

    description = (
        "Calculate cryptographic and perceptual "
        "hashes for image evidence."
    )

    version = "1.0"

    DEFAULT_HASH_SIZE = 16

    DEFAULT_CHUNK_SIZE = (
        1024
        * 1024
    )

    SUPPORTED_CRYPTOGRAPHIC_HASHES = (
        "md5",
        "sha1",
        "sha256",
        "sha512",
    )

    SUPPORTED_PERCEPTUAL_HASHES = (
        "average_hash",
        "difference_hash",
        "perceptual_hash",
        "wavelet_hash",
        "color_hash",
    )

    # ==========================================================
    # Availability
    # ==========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether the optional ImageHash dependency exists.
        """

        return (
            importlib.util.find_spec(
                "imagehash"
            )
            is not None
        )

    def unavailable_reason(
        self,
    ) -> str:
        """
        Explain how to install ImageHash.
        """

        return (
            "The ImageHash package is not installed. "
            "Install it with: "
            "python -m pip install ImageHash"
        )

    # ==========================================================
    # Analysis
    # ==========================================================

    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:
        """
        Calculate all configured image hashes.
        """

        import imagehash

        hash_size = self._normalize_hash_size(
            context.get_option(
                "hash_size",
                self.DEFAULT_HASH_SIZE,
            )
        )

        chunk_size = self._normalize_chunk_size(
            context.get_option(
                "chunk_size",
                self.DEFAULT_CHUNK_SIZE,
            )
        )

        warnings: list[str] = []

        cryptographic_hashes = (
            self._calculate_cryptographic_hashes(
                path=context.original_path,
                chunk_size=chunk_size,
            )
        )

        perceptual_hashes: dict[
            str,
            str | None,
        ] = {
            "average_hash": None,
            "difference_hash": None,
            "perceptual_hash": None,
            "wavelet_hash": None,
            "color_hash": None,
        }

        analysis_path = (
            context.analysis_path
        )

        try:

            with Image.open(
                analysis_path
            ) as source_image:

                if bool(
                    getattr(
                        source_image,
                        "is_animated",
                        False,
                    )
                ):

                    source_image.seek(
                        0
                    )

                    warnings.append(
                        (
                            "The source is animated; "
                            "perceptual hashes were calculated "
                            "from the first frame only."
                        )
                    )

                source_image.load()

                oriented_image = (
                    ImageOps.exif_transpose(
                        source_image
                    )
                )

                normalized_image = (
                    self._normalize_image(
                        oriented_image
                    )
                )

                perceptual_hashes[
                    "average_hash"
                ] = str(
                    imagehash.average_hash(
                        normalized_image,
                        hash_size=hash_size,
                    )
                )

                perceptual_hashes[
                    "difference_hash"
                ] = str(
                    imagehash.dhash(
                        normalized_image,
                        hash_size=hash_size,
                    )
                )

                perceptual_hashes[
                    "perceptual_hash"
                ] = str(
                    imagehash.phash(
                        normalized_image,
                        hash_size=hash_size,
                    )
                )

                perceptual_hashes[
                    "wavelet_hash"
                ] = str(
                    imagehash.whash(
                        normalized_image,
                        hash_size=hash_size,
                    )
                )

                perceptual_hashes[
                    "color_hash"
                ] = str(
                    imagehash.colorhash(
                        normalized_image
                    )
                )

        except UnidentifiedImageError as error:

            warnings.append(
                (
                    "Perceptual hashes could not be "
                    "calculated because the analysis "
                    f"image is unreadable: {error}"
                )
            )

        except OSError as error:

            warnings.append(
                (
                    "Perceptual hash calculation failed: "
                    f"{error}"
                )
            )

        data = {
            "cryptographic": (
                cryptographic_hashes
            ),
            "perceptual": (
                perceptual_hashes
            ),
            "md5": (
                cryptographic_hashes.get(
                    "md5"
                )
            ),
            "sha1": (
                cryptographic_hashes.get(
                    "sha1"
                )
            ),
            "sha256": (
                cryptographic_hashes.get(
                    "sha256"
                )
            ),
            "sha512": (
                cryptographic_hashes.get(
                    "sha512"
                )
            ),
            "average_hash": (
                perceptual_hashes.get(
                    "average_hash"
                )
            ),
            "difference_hash": (
                perceptual_hashes.get(
                    "difference_hash"
                )
            ),
            "perceptual_hash": (
                perceptual_hashes.get(
                    "perceptual_hash"
                )
            ),
            "wavelet_hash": (
                perceptual_hashes.get(
                    "wavelet_hash"
                )
            ),
            "color_hash": (
                perceptual_hashes.get(
                    "color_hash"
                )
            ),
            "hash_size": hash_size,
            "original_path": str(
                context.original_path
            ),
            "analysis_path": str(
                analysis_path
            ),
            "analysis_uses_preview": (
                analysis_path
                != context.original_path
            ),
        }

        return ImageAnalysisResult.completed(
            analyzer=self.name,
            data=data,
            warnings=warnings,
            metadata=self.metadata(),
        )

    # ==========================================================
    # Cryptographic hashes
    # ==========================================================

    def _calculate_cryptographic_hashes(
        self,
        *,
        path: Path,
        chunk_size: int,
    ) -> dict[str, str]:
        """
        Calculate all cryptographic hashes in one file pass.
        """

        digest_objects = {
            "md5": hashlib.md5(
                usedforsecurity=False
            ),
            "sha1": hashlib.sha1(
                usedforsecurity=False
            ),
            "sha256": hashlib.sha256(),
            "sha512": hashlib.sha512(),
        }

        with path.open(
            "rb"
        ) as source_file:

            while True:

                chunk = source_file.read(
                    chunk_size
                )

                if not chunk:

                    break

                for digest in (
                    digest_objects.values()
                ):

                    digest.update(
                        chunk
                    )

        return {
            name: digest.hexdigest()
            for name, digest
            in digest_objects.items()
        }

    # ==========================================================
    # Image normalization
    # ==========================================================

    @staticmethod
    def _normalize_image(
        image: Image.Image,
    ) -> Image.Image:
        """
        Convert image to a stable RGB representation.
        """

        if image.mode == "RGB":

            return image.copy()

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                (
                    255,
                    255,
                    255,
                ),
            )

            alpha_channel = (
                image.getchannel(
                    "A"
                )
            )

            background.paste(
                image,
                mask=alpha_channel,
            )

            return background

        if image.mode in {
            "LA",
            "PA",
        }:

            rgba_image = image.convert(
                "RGBA"
            )

            return (
                ImageHashAnalyzer
                ._normalize_image(
                    rgba_image
                )
            )

        if (
            image.mode == "P"
            and "transparency"
            in image.info
        ):

            return (
                ImageHashAnalyzer
                ._normalize_image(
                    image.convert(
                        "RGBA"
                    )
                )
            )

        return image.convert(
            "RGB"
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_hash_size(
        value: Any,
    ) -> int:
        """
        Validate perceptual hash dimensions.
        """

        try:

            hash_size = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "hash_size must be an integer."
            ) from error

        if hash_size < 4:

            raise ValueError(
                "hash_size must be at least 4."
            )

        if hash_size > 64:

            raise ValueError(
                "hash_size must not exceed 64."
            )

        return hash_size

    @staticmethod
    def _normalize_chunk_size(
        value: Any,
    ) -> int:
        """
        Validate streaming chunk size.
        """

        try:

            chunk_size = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "chunk_size must be an integer."
            ) from error

        if chunk_size < 4096:

            raise ValueError(
                "chunk_size must be at least 4096 bytes."
            )

        if chunk_size > (
            64
            * 1024
            * 1024
        ):

            raise ValueError(
                (
                    "chunk_size must not exceed "
                    "64 megabytes."
                )
            )

        return chunk_size

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return analyzer information.
        """

        base_metadata = super().metadata()

        return {
            **base_metadata,
            "cryptographic_hashes": list(
                self.SUPPORTED_CRYPTOGRAPHIC_HASHES
            ),
            "perceptual_hashes": list(
                self.SUPPORTED_PERCEPTUAL_HASHES
            ),
            "default_hash_size": (
                self.DEFAULT_HASH_SIZE
            ),
            "cryptographic_source": (
                "original_evidence"
            ),
            "perceptual_source": (
                "analysis_path"
            ),
        }