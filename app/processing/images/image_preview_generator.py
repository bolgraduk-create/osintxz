"""
Image preview generator.

Creates high-quality, display-compatible previews
for the desktop image viewer.

The preview is separate from the small thumbnail:

- thumbnail: compact WebP for the image library
- preview: high-quality PNG for the central viewer

Responsible for:

- opening images through Pillow
- decoding HEIC and HEIF through pillow-heif
- applying EXIF display orientation
- extracting the first frame from animated images
- converting unsupported color modes
- creating a lossless PNG preview
- preserving source resolution when reasonable
- reusing cached previews
- preserving the original evidence file

Does NOT:

- modify original files
- access the database
- create artifacts
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


class ImagePreviewGenerator:
    """
    Generate cached high-quality PNG previews.
    """

    DEFAULT_MAXIMUM_WIDTH = 8192

    DEFAULT_MAXIMUM_HEIGHT = 8192

    OUTPUT_FORMAT = "PNG"

    OUTPUT_EXTENSION = ".png"

    OUTPUT_MIME_TYPE = "image/png"

    def __init__(
        self,
        *,
        previews_directory: str | Path,
        maximum_width: int = DEFAULT_MAXIMUM_WIDTH,
        maximum_height: int = DEFAULT_MAXIMUM_HEIGHT,
    ) -> None:
        """
        Initialize preview generator.
        """

        self.previews_directory = Path(
            previews_directory
        ).expanduser().resolve()

        self.maximum_width = (
            self._validate_dimension(
                maximum_width,
                field_name="maximum_width",
            )
        )

        self.maximum_height = (
            self._validate_dimension(
                maximum_height,
                field_name="maximum_height",
            )
        )

        self.previews_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def generate(
        self,
        image_path: str | Path,
        *,
        sha256: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Generate or reuse a lossless image preview.
        """

        source_path = self._validate_source_path(
            image_path
        )

        normalized_sha256 = (
            self._normalize_sha256(
                sha256
            )
        )

        if normalized_sha256 is None:

            normalized_sha256 = (
                self._calculate_sha256(
                    source_path
                )
            )

        destination_path = (
            self._build_destination_path(
                normalized_sha256
            )
        )

        if (
            destination_path.is_file()
            and not force
        ):

            existing_metadata = (
                self._inspect_existing_preview(
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
                "created": False,
                "reused": True,
                "status": "completed",
            }

        temporary_path = (
            destination_path.with_name(
                destination_path.stem
                + ".temporary"
                + self.OUTPUT_EXTENSION
            )
        )

        try:

            generated_metadata = (
                self._create_preview(
                    source_path=source_path,
                    temporary_path=temporary_path,
                )
            )

            temporary_path.replace(
                destination_path
            )

            return {
                **generated_metadata,
                "preview_path": str(
                    destination_path
                ),
                "preview_size_bytes": (
                    destination_path
                    .stat()
                    .st_size
                ),
                "source_path": str(
                    source_path
                ),
                "source_sha256": (
                    normalized_sha256
                ),
                "created": True,
                "reused": False,
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
    # Preview creation
    # ==========================================================

    def _create_preview(
        self,
        *,
        source_path: Path,
        temporary_path: Path,
    ) -> dict[str, Any]:
        """
        Create one lossless PNG preview.
        """

        try:

            with Image.open(
                source_path
            ) as source_image:

                is_animated = bool(
                    getattr(
                        source_image,
                        "is_animated",
                        False,
                    )
                )

                if is_animated:

                    source_image.seek(
                        0
                    )

                source_image.load()

                original_icc_profile = (
                    source_image.info.get(
                        "icc_profile"
                    )
                )

                oriented_image = (
                    ImageOps.exif_transpose(
                        source_image
                    )
                )

                prepared_image = (
                    self._prepare_for_png(
                        oriented_image
                    )
                )

                source_width, source_height = (
                    prepared_image.size
                )

                preview_image = (
                    prepared_image.copy()
                )

                resized = (
                    source_width
                    > self.maximum_width
                    or source_height
                    > self.maximum_height
                )

                if resized:

                    preview_image.thumbnail(
                        (
                            self.maximum_width,
                            self.maximum_height,
                        ),
                        resample=(
                            Image.Resampling.LANCZOS
                        ),
                    )

                preview_width, preview_height = (
                    preview_image.size
                )

                temporary_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                save_options: dict[str, Any] = {
                    "format": self.OUTPUT_FORMAT,
                    "compress_level": 3,
                    "optimize": False,
                }

                if original_icc_profile:

                    save_options[
                        "icc_profile"
                    ] = original_icc_profile

                preview_image.save(
                    temporary_path,
                    **save_options,
                )

                return {
                    "preview_path": str(
                        temporary_path
                    ),
                    "preview_format": (
                        self.OUTPUT_FORMAT
                    ),
                    "preview_mime_type": (
                        self.OUTPUT_MIME_TYPE
                    ),
                    "preview_width": (
                        preview_width
                    ),
                    "preview_height": (
                        preview_height
                    ),
                    "preview_size_bytes": (
                        temporary_path
                        .stat()
                        .st_size
                    ),
                    "source_display_width": (
                        source_width
                    ),
                    "source_display_height": (
                        source_height
                    ),
                    "maximum_width": (
                        self.maximum_width
                    ),
                    "maximum_height": (
                        self.maximum_height
                    ),
                    "resized": resized,
                    "lossless": True,
                    "icc_profile_preserved": bool(
                        original_icc_profile
                    ),
                    "first_frame_only": (
                        is_animated
                    ),
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
                "Unable to generate image preview for "
                f"'{source_path}': {error}"
            ) from error

    # ==========================================================
    # Existing previews
    # ==========================================================

    def _inspect_existing_preview(
        self,
        preview_path: Path,
    ) -> dict[str, Any]:
        """
        Read an existing preview.
        """

        try:

            with Image.open(
                preview_path
            ) as preview_image:

                width, height = (
                    preview_image.size
                )

                preview_format = str(
                    preview_image.format
                    or self.OUTPUT_FORMAT
                ).upper()

                icc_profile_present = bool(
                    preview_image.info.get(
                        "icc_profile"
                    )
                )

        except (
            UnidentifiedImageError,
            OSError,
        ) as error:

            raise ValueError(
                "Existing preview is unreadable: "
                f"{preview_path}"
            ) from error

        return {
            "preview_path": str(
                preview_path
            ),
            "preview_format": (
                preview_format
            ),
            "preview_mime_type": (
                self.OUTPUT_MIME_TYPE
            ),
            "preview_width": width,
            "preview_height": height,
            "preview_size_bytes": (
                preview_path
                .stat()
                .st_size
            ),
            "maximum_width": (
                self.maximum_width
            ),
            "maximum_height": (
                self.maximum_height
            ),
            "lossless": True,
            "icc_profile_preserved": (
                icc_profile_present
            ),
            "generator": (
                self.__class__.__name__
            ),
        }

    # ==========================================================
    # Image preparation
    # ==========================================================

    @staticmethod
    def _prepare_for_png(
        image: Image.Image,
    ) -> Image.Image:
        """
        Convert an image to a PNG-compatible display mode.
        """

        if image.mode in {
            "RGB",
            "RGBA",
            "L",
            "LA",
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

        if image.mode == "P":

            return image.convert(
                "RGB"
            )

        if image.mode in {
            "CMYK",
            "YCbCr",
            "LAB",
            "HSV",
            "I",
            "F",
        }:

            return image.convert(
                "RGB"
            )

        return image.convert(
            "RGBA"
        )

    # ==========================================================
    # Paths
    # ==========================================================

    def _build_destination_path(
        self,
        sha256: str,
    ) -> Path:
        """
        Build deterministic preview path.
        """

        prefix_directory = (
            self.previews_directory
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
        Calculate SHA-256 of the original file.
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
        Validate optional SHA-256.
        """

        if value is None:

            return None

        normalized = str(
            value
        ).strip().lower()

        if not normalized:

            return None

        if (
            len(
                normalized
            ) != 64
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
                "Image file does not exist: "
                f"{source_path}"
            ) from error

        if not source_path.is_file():

            raise ValueError(
                "Image path is not a file: "
                f"{source_path}"
            )

        return source_path

    @staticmethod
    def _validate_dimension(
        value: int,
        *,
        field_name: str,
    ) -> int:
        """
        Validate preview dimension.
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

        if normalized > 16384:

            raise ValueError(
                f"{field_name} must not exceed 16384."
            )

        return normalized

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return generator information.
        """

        return {
            "type": (
                "image_preview_generator"
            ),
            "engine": "Pillow",
            "output_format": (
                self.OUTPUT_FORMAT
            ),
            "output_extension": (
                self.OUTPUT_EXTENSION
            ),
            "lossless": True,
            "maximum_width": (
                self.maximum_width
            ),
            "maximum_height": (
                self.maximum_height
            ),
            "previews_directory": str(
                self.previews_directory
            ),
        }