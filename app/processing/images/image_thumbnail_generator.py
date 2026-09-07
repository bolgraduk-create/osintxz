"""
Image thumbnail generator.

Creates cached preview images for imported image evidence.

Responsible for:

- validating source image paths
- correcting EXIF display orientation
- generating proportionally scaled previews
- storing thumbnails in managed storage
- reusing previously generated thumbnails
- returning thumbnail metadata

Does NOT:

- modify original evidence files
- access the database
- create Artifact records
- commit transactions
- execute OCR or AI analysis
"""

from __future__ import annotations

import hashlib

from pathlib import Path
from typing import Any

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)


class ImageThumbnailGenerator:
    """
    Generates cached WebP thumbnails for images.
    """

    DEFAULT_MAX_WIDTH = 320

    DEFAULT_MAX_HEIGHT = 240

    DEFAULT_QUALITY = 82

    OUTPUT_FORMAT = "WEBP"

    OUTPUT_EXTENSION = ".webp"

    def __init__(
        self,
        *,
        thumbnails_directory: str | Path,
        maximum_width: int = DEFAULT_MAX_WIDTH,
        maximum_height: int = DEFAULT_MAX_HEIGHT,
        quality: int = DEFAULT_QUALITY,
    ) -> None:
        """
        Initialize thumbnail generator.
        """

        self.thumbnails_directory = Path(
            thumbnails_directory
        ).expanduser().resolve()

        self.maximum_width = self._validate_dimension(
            maximum_width,
            field_name="maximum_width",
        )

        self.maximum_height = self._validate_dimension(
            maximum_height,
            field_name="maximum_height",
        )

        self.quality = self._validate_quality(
            quality
        )

        self.thumbnails_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ==========================================================
    # Generation
    # ==========================================================

    def generate(
        self,
        image_path: str | Path,
        *,
        sha256: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Generate or reuse a thumbnail.

        Args:
            image_path:
                Original image path.

            sha256:
                Optional precomputed SHA-256 of the original.
                When omitted, it is calculated here.

            force:
                Replace an existing thumbnail when True.

        Returns:
            Thumbnail metadata dictionary.
        """

        source_path = self._validate_source_path(
            image_path
        )

        normalized_sha256 = self._normalize_sha256(
            sha256
        )

        if normalized_sha256 is None:

            normalized_sha256 = self._calculate_sha256(
                source_path
            )

        destination_path = self._build_destination_path(
            normalized_sha256
        )

        if (
            destination_path.is_file()
            and not force
        ):

            existing_metadata = (
                self._inspect_existing_thumbnail(
                    destination_path
                )
            )

            return {
                **existing_metadata,
                "source_path": str(
                    source_path
                ),
                "source_sha256": (
                    normalized_sha256
                ),
                "reused": True,
                "created": False,
                "status": "completed",
            }

        temporary_path = destination_path.with_suffix(
            ".temporary.webp"
        )

        try:

            generated_metadata = (
                self._create_thumbnail(
                    source_path=source_path,
                    temporary_path=temporary_path,
                )
            )

            temporary_path.replace(
                destination_path
            )

            return {
                **generated_metadata,
                "source_path": str(
                    source_path
                ),
                "source_sha256": (
                    normalized_sha256
                ),
                "thumbnail_path": str(
                    destination_path
                ),
                "reused": False,
                "created": True,
                "status": "completed",
            }

        except Exception:

            if temporary_path.exists():

                try:

                    temporary_path.unlink()

                except OSError:

                    pass

            raise

    # ==========================================================
    # Image creation
    # ==========================================================

    def _create_thumbnail(
        self,
        *,
        source_path: Path,
        temporary_path: Path,
    ) -> dict[str, Any]:
        """
        Create one WebP thumbnail.
        """

        try:

            with Image.open(
                source_path
            ) as source_image:

                source_image.load()

                oriented_image = ImageOps.exif_transpose(
                    source_image
                )

                prepared_image = self._prepare_for_webp(
                    oriented_image
                )

                original_width, original_height = (
                    prepared_image.size
                )

                thumbnail_image = prepared_image.copy()

                thumbnail_image.thumbnail(
                    (
                        self.maximum_width,
                        self.maximum_height,
                    ),
                    resample=(
                        Image.Resampling.LANCZOS
                    ),
                )

                thumbnail_width, thumbnail_height = (
                    thumbnail_image.size
                )

                temporary_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                save_options: dict[str, Any] = {
                    "format": self.OUTPUT_FORMAT,
                    "quality": self.quality,
                    "method": 6,
                }

                if self._has_alpha(
                    thumbnail_image
                ):

                    save_options["lossless"] = True

                thumbnail_image.save(
                    temporary_path,
                    **save_options,
                )

                return {
                    "thumbnail_path": str(
                        temporary_path
                    ),
                    "thumbnail_format": (
                        self.OUTPUT_FORMAT
                    ),
                    "thumbnail_mime_type": (
                        "image/webp"
                    ),
                    "thumbnail_width": (
                        thumbnail_width
                    ),
                    "thumbnail_height": (
                        thumbnail_height
                    ),
                    "thumbnail_size_bytes": (
                        temporary_path
                        .stat()
                        .st_size
                    ),
                    "source_display_width": (
                        original_width
                    ),
                    "source_display_height": (
                        original_height
                    ),
                    "maximum_width": (
                        self.maximum_width
                    ),
                    "maximum_height": (
                        self.maximum_height
                    ),
                    "quality": self.quality,
                    "generator": (
                        self.__class__.__name__
                    ),
                }

        except UnidentifiedImageError as error:

            raise ValueError(
                "The file is not a recognizable image: "
                f"{source_path}"
            ) from error

        except OSError as error:

            raise ValueError(
                "Unable to generate thumbnail for "
                f"'{source_path}': {error}"
            ) from error

    @staticmethod
    def _prepare_for_webp(
        image: Image.Image,
    ) -> Image.Image:
        """
        Convert image to a WebP-compatible color mode.
        """

        if image.mode in {
            "RGB",
            "RGBA",
        }:

            return image

        if (
            image.mode == "P"
            and "transparency"
            in image.info
        ):

            return image.convert(
                "RGBA"
            )

        if image.mode in {
            "LA",
            "PA",
        }:

            return image.convert(
                "RGBA"
            )

        return image.convert(
            "RGB"
        )

    # ==========================================================
    # Existing thumbnail
    # ==========================================================

    def _inspect_existing_thumbnail(
        self,
        thumbnail_path: Path,
    ) -> dict[str, Any]:
        """
        Read metadata from an existing thumbnail.
        """

        try:

            with Image.open(
                thumbnail_path
            ) as thumbnail_image:

                width, height = (
                    thumbnail_image.size
                )

                image_format = str(
                    thumbnail_image.format
                    or self.OUTPUT_FORMAT
                ).upper()

        except (
            UnidentifiedImageError,
            OSError,
        ) as error:

            raise ValueError(
                "Existing thumbnail is unreadable: "
                f"{thumbnail_path}"
            ) from error

        return {
            "thumbnail_path": str(
                thumbnail_path
            ),
            "thumbnail_format": image_format,
            "thumbnail_mime_type": "image/webp",
            "thumbnail_width": width,
            "thumbnail_height": height,
            "thumbnail_size_bytes": (
                thumbnail_path.stat().st_size
            ),
            "maximum_width": (
                self.maximum_width
            ),
            "maximum_height": (
                self.maximum_height
            ),
            "quality": self.quality,
            "generator": (
                self.__class__.__name__
            ),
        }

    # ==========================================================
    # Paths
    # ==========================================================

    def _build_destination_path(
        self,
        sha256: str,
    ) -> Path:
        """
        Build deterministic thumbnail path.
        """

        prefix_directory = (
            self.thumbnails_directory
            / sha256[:2]
        )

        prefix_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return (
            prefix_directory
            / f"{sha256}{self.OUTPUT_EXTENSION}"
        )

    # ==========================================================
    # Hashing
    # ==========================================================

    @staticmethod
    def _calculate_sha256(
        path: Path,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> str:
        """
        Calculate SHA-256 without loading the file into memory.
        """

        digest = hashlib.sha256()

        with path.open(
            "rb"
        ) as source_file:

            while True:

                chunk = source_file.read(
                    chunk_size
                )

                if not chunk:

                    break

                digest.update(
                    chunk
                )

        return digest.hexdigest()

    @staticmethod
    def _normalize_sha256(
        value: str | None,
    ) -> str | None:
        """
        Validate optional SHA-256 value.
        """

        if value is None:

            return None

        normalized = str(
            value
        ).strip().lower()

        if not normalized:

            return None

        if (
            len(normalized) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in normalized
            )
        ):

            raise ValueError(
                "sha256 must contain exactly "
                "64 hexadecimal characters."
            )

        return normalized

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_source_path(
        image_path: str | Path,
    ) -> Path:
        """
        Validate source image path.
        """

        source_path = Path(
            image_path
        ).expanduser()

        try:

            source_path = source_path.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                f"Image file does not exist: {source_path}"
            ) from error

        if not source_path.is_file():

            raise ValueError(
                f"Image path is not a file: {source_path}"
            )

        return source_path

    @staticmethod
    def _validate_dimension(
        value: int,
        *,
        field_name: str,
    ) -> int:
        """
        Validate maximum thumbnail dimension.
        """

        try:

            normalized = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                f"{field_name} must be an integer."
            ) from error

        if normalized <= 0:

            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        if normalized > 8192:

            raise ValueError(
                f"{field_name} is unreasonably large."
            )

        return normalized

    @staticmethod
    def _validate_quality(
        value: int,
    ) -> int:
        """
        Validate WebP quality.
        """

        try:

            normalized = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "quality must be an integer."
            ) from error

        if not 1 <= normalized <= 100:

            raise ValueError(
                "quality must be between 1 and 100."
            )

        return normalized

    @staticmethod
    def _has_alpha(
        image: Image.Image,
    ) -> bool:
        """
        Detect image transparency.
        """

        if image.mode in {
            "RGBA",
            "LA",
            "PA",
        }:

            return True

        return (
            image.mode == "P"
            and "transparency"
            in image.info
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return generator information.
        """

        return {
            "type": (
                "image_thumbnail_generator"
            ),
            "engine": "Pillow",
            "output_format": (
                self.OUTPUT_FORMAT
            ),
            "output_extension": (
                self.OUTPUT_EXTENSION
            ),
            "maximum_width": (
                self.maximum_width
            ),
            "maximum_height": (
                self.maximum_height
            ),
            "quality": self.quality,
            "thumbnails_directory": str(
                self.thumbnails_directory
            ),
        }