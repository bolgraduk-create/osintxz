"""
Image metadata extractor.

Extracts safe technical information from image files.

Responsible for:

- validating image readability
- detecting image format
- reading width and height
- reading color mode
- calculating aspect ratio
- detecting transparency
- detecting animation and frame count
- reading basic orientation information
- returning normalized technical metadata

Does NOT:

- modify original images
- extract complete EXIF, XMP or IPTC metadata
- execute OCR
- detect faces or objects
- access the database
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import (
    Image,
    UnidentifiedImageError,
)


class ImageMetadataExtractor:
    """
    Extracts basic technical metadata through Pillow.
    """

    ORIENTATION_TAG_ID = 274

    ORIENTATION_NAMES = {
        1: "normal",
        2: "mirrored_horizontal",
        3: "rotated_180",
        4: "mirrored_vertical",
        5: "mirrored_horizontal_rotated_270",
        6: "rotated_90",
        7: "mirrored_horizontal_rotated_90",
        8: "rotated_270",
    }

    def extract(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Extract technical metadata from one image.

        The complete image is not retained in memory after this
        method returns.
        """

        image_path = self._validate_path(
            path
        )

        try:

            with Image.open(
                image_path
            ) as image:

                image.verify()

            with Image.open(
                image_path
            ) as image:

                width, height = image.size

                image_format = self._normalize_format(
                    image.format,
                    image_path,
                )

                color_mode = str(
                    image.mode
                    or ""
                )

                frame_count = self._frame_count(
                    image
                )

                orientation_value = (
                    self._read_orientation(
                        image
                    )
                )

                aspect_ratio = (
                    self._aspect_ratio(
                        width,
                        height,
                    )
                )

                return {
                    "width": width,
                    "height": height,
                    "dimensions": {
                        "width": width,
                        "height": height,
                    },
                    "megapixels": (
                        self._megapixels(
                            width,
                            height,
                        )
                    ),
                    "aspect_ratio": aspect_ratio,
                    "orientation": (
                        self._visual_orientation(
                            width,
                            height,
                        )
                    ),
                    "exif_orientation": (
                        orientation_value
                    ),
                    "exif_orientation_name": (
                        self.ORIENTATION_NAMES.get(
                            orientation_value,
                            "unknown",
                        )
                        if orientation_value
                        is not None
                        else None
                    ),
                    "image_format": image_format,
                    "color_mode": color_mode,
                    "color_bands": list(
                        image.getbands()
                    ),
                    "has_alpha": (
                        self._has_alpha(
                            image
                        )
                    ),
                    "is_animated": bool(
                        getattr(
                            image,
                            "is_animated",
                            False,
                        )
                    ),
                    "frame_count": frame_count,
                    "dpi": (
                        self._normalize_dpi(
                            image.info.get(
                                "dpi"
                            )
                        )
                    ),
                    "icc_profile_present": bool(
                        image.info.get(
                            "icc_profile"
                        )
                    ),
                    "exif_present": bool(
                        image.info.get(
                            "exif"
                        )
                    ),
                    "metadata_extractor": (
                        self.__class__.__name__
                    ),
                }

        except UnidentifiedImageError as error:

            raise ValueError(
                "The file is not a supported or recognizable image: "
                f"{image_path}"
            ) from error

        except OSError as error:

            raise ValueError(
                "The image could not be read: "
                f"{image_path}. "
                f"Reason: {error}"
            ) from error

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_path(
        path: str | Path,
    ) -> Path:
        """
        Validate and normalize an image path.
        """

        image_path = Path(
            path
        ).expanduser()

        try:

            image_path = image_path.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                f"Image file does not exist: {image_path}"
            ) from error

        if not image_path.is_file():

            raise ValueError(
                f"Image path is not a file: {image_path}"
            )

        return image_path

    # ==========================================================
    # Dimensions
    # ==========================================================

    @staticmethod
    def _megapixels(
        width: int,
        height: int,
    ) -> float:
        """
        Calculate megapixel count.
        """

        if (
            width <= 0
            or height <= 0
        ):

            return 0.0

        return round(
            (
                width
                * height
            )
            / 1_000_000,
            3,
        )

    @staticmethod
    def _aspect_ratio(
        width: int,
        height: int,
    ) -> float | None:
        """
        Calculate normalized decimal aspect ratio.
        """

        if (
            width <= 0
            or height <= 0
        ):

            return None

        return round(
            width / height,
            4,
        )

    @staticmethod
    def _visual_orientation(
        width: int,
        height: int,
    ) -> str:
        """
        Classify image geometry.
        """

        if width > height:

            return "landscape"

        if height > width:

            return "portrait"

        return "square"

    # ==========================================================
    # Format
    # ==========================================================

    @staticmethod
    def _normalize_format(
        detected_format: str | None,
        path: Path,
    ) -> str:
        """
        Normalize image format name.
        """

        if detected_format:

            return str(
                detected_format
            ).upper()

        suffix = (
            path.suffix
            .lower()
            .lstrip(".")
        )

        if suffix in {
            "jpg",
            "jpeg",
        }:

            return "JPEG"

        if suffix:

            return suffix.upper()

        return "UNKNOWN"

    # ==========================================================
    # Color
    # ==========================================================

    @staticmethod
    def _has_alpha(
        image: Image.Image,
    ) -> bool:
        """
        Return whether image contains transparency information.
        """

        if image.mode in {
            "RGBA",
            "LA",
            "PA",
        }:

            return True

        if (
            image.mode == "P"
            and "transparency"
            in image.info
        ):

            return True

        return False

    # ==========================================================
    # Animation
    # ==========================================================

    @staticmethod
    def _frame_count(
        image: Image.Image,
    ) -> int:
        """
        Return number of image frames.
        """

        try:

            frame_count = int(
                getattr(
                    image,
                    "n_frames",
                    1,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            frame_count = 1

        return max(
            1,
            frame_count,
        )

    # ==========================================================
    # Orientation
    # ==========================================================

    def _read_orientation(
        self,
        image: Image.Image,
    ) -> int | None:
        """
        Read standard EXIF orientation value.

        Complete EXIF extraction will be handled by ExifTool later.
        """

        try:

            exif = image.getexif()

        except (
            AttributeError,
            OSError,
        ):

            return None

        if not exif:

            return None

        orientation = exif.get(
            self.ORIENTATION_TAG_ID
        )

        if orientation is None:

            return None

        try:

            return int(
                orientation
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    # ==========================================================
    # DPI
    # ==========================================================

    @staticmethod
    def _normalize_dpi(
        value: Any,
    ) -> dict[str, float] | None:
        """
        Normalize Pillow DPI information.
        """

        if not isinstance(
            value,
            (
                tuple,
                list,
            ),
        ):

            return None

        if len(
            value
        ) < 2:

            return None

        try:

            horizontal = float(
                value[0]
            )

            vertical = float(
                value[1]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        return {
            "horizontal": round(
                horizontal,
                3,
            ),
            "vertical": round(
                vertical,
                3,
            ),
        }

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return extractor information.
        """

        return {
            "type": (
                "image_metadata_extractor"
            ),
            "engine": "Pillow",
            "capabilities": [
                "dimensions",
                "format",
                "color_mode",
                "color_bands",
                "alpha",
                "aspect_ratio",
                "orientation",
                "animation",
                "frame_count",
                "dpi",
                "profile_presence",
            ],
        }