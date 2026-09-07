"""
Image processor.

Responsible for:

- basic file inspection
- technical image metadata extraction
- cached thumbnail generation
- complete EXIF/XMP/IPTC metadata extraction

Uses:

- FileProcessor
- ImageMetadataExtractor
- ImageThumbnailGenerator
- ImageExifExtractor

Advanced image analysis such as:

- OCR
- QR and barcode detection
- perceptual hashing
- face detection
- object detection
- integrity analysis
- multimodal AI analysis

will be implemented through separate processing components.

Does not:

- access the database
- modify original evidence files
- commit transactions
- create entities or timeline events
"""

from __future__ import annotations

import mimetypes

from pathlib import Path
from typing import Any

from app.core.config import (
    THUMBNAILS_DIR,
)

from app.processing.base_processor import (
    BaseProcessor,
)

from app.processing.file_processor import (
    FileProcessor,
)

from app.processing.images.image_exif_extractor import (
    ImageExifExtractor,
)

from app.processing.images.image_metadata_extractor import (
    ImageMetadataExtractor,
)

from app.processing.images.image_thumbnail_generator import (
    ImageThumbnailGenerator,
)

from app.core.config import (
    PREVIEWS_DIR,
    THUMBNAILS_DIR,
)

from app.processing.images.image_preview_generator import (
    ImagePreviewGenerator,
)


class ImageProcessor(
    BaseProcessor,
):
    """
    Process image files and prepare
    application-ready metadata.
    """

    SUPPORTED_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
    }

    def __init__(
        self,
        file_processor: FileProcessor | None = None,
        metadata_extractor: (
            ImageMetadataExtractor | None
        ) = None,
        thumbnail_generator: (
            ImageThumbnailGenerator | None
        ) = None,
        preview_generator: (
            ImagePreviewGenerator | None
        ) = None,
        exif_extractor: (
            ImageExifExtractor | None
        ) = None,
    ) -> None:
        """
        Initialize image processor dependencies.
        """

        self.file_processor = (
            file_processor
            or FileProcessor()
        )

        self.metadata_extractor = (
            metadata_extractor
            or ImageMetadataExtractor()
        )

        self.thumbnail_generator = (
            thumbnail_generator
            or ImageThumbnailGenerator(
                thumbnails_directory=(
                    THUMBNAILS_DIR
                ),
            )
        )


        self.preview_generator = (
            preview_generator
            or ImagePreviewGenerator(
                previews_directory=(
                    PREVIEWS_DIR
                ),
            )
        )

        self.exif_extractor = (
            exif_extractor
            or ImageExifExtractor()
        )

    # ==========================================================
    # Processing
    # ==========================================================

    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Inspect an image and execute the base image pipeline.

        Thumbnail and ExifTool failures are non-fatal.
        """

        file_metadata = (
            self.file_processor.process(
                data
            )
        )

        extension = str(
            file_metadata.get(
                "extension",
                "",
            )
        ).lower()

        if extension not in self.SUPPORTED_EXTENSIONS:

            raise ValueError(
                "Unsupported image extension: "
                f"{extension or 'unknown'}"
            )

        file_path = Path(
            file_metadata["path"]
        )

        mime_type, _ = mimetypes.guess_type(
            file_path.name
        )

        image_metadata = (
            self.metadata_extractor.extract(
                file_path
            )
        )

        warnings: list[str] = []

        thumbnail_metadata = (
            self._generate_thumbnail(
                file_path=file_path,
                sha256=(
                    file_metadata.get(
                        "sha256"
                    )
                ),
                warnings=warnings,
            )
        )

        preview_metadata = (
            self._generate_preview(
                file_path=file_path,
                sha256=(
                    file_metadata.get(
                        "sha256"
                    )
                ),
                warnings=warnings,
            )
        )

        exif_metadata = (
            self._extract_exif(
                file_path=file_path,
                warnings=warnings,
            )
        )

        result: dict[str, Any] = {
            **file_metadata,
            **image_metadata,
            "processor": (
                self.__class__.__name__
            ),
            "category": "image",
            "mime_type": (
                mime_type
                or "application/octet-stream"
            ),
            "supported": True,
            "processing_status": "completed",
            "warnings": warnings,
            "exif": exif_metadata,
        }

        self._attach_thumbnail_metadata(
            result=result,
            thumbnail_metadata=(
                thumbnail_metadata
            ),
        )

        self._attach_preview_metadata(
            result=result,
            preview_metadata=(
                preview_metadata
            ),
        )

        self._attach_normalized_exif_fields(
            result=result,
            exif_metadata=exif_metadata,
        )

        return result

    # ==========================================================
    # Thumbnail
    # ==========================================================

    def _generate_thumbnail(
        self,
        *,
        file_path: Path,
        sha256: Any,
        warnings: list[str],
    ) -> dict[str, Any] | None:
        """
        Generate a cached image thumbnail.

        Failure does not interrupt image import.
        """

        try:

            return (
                self.thumbnail_generator
                .generate(
                    image_path=file_path,
                    sha256=(
                        str(
                            sha256
                        )
                        if sha256
                        else None
                    ),
                )
            )

        except Exception as error:

            warnings.append(
                "Thumbnail generation failed: "
                f"{error}"
            )

            return None

    @staticmethod
    def _attach_thumbnail_metadata(
        *,
        result: dict[str, Any],
        thumbnail_metadata: (
            dict[str, Any] | None
        ),
    ) -> None:
        """
        Add normalized thumbnail fields to processing result.
        """

        if thumbnail_metadata is None:

            result["thumbnail"] = None

            result["thumbnail_path"] = None

            return

        result["thumbnail"] = (
            thumbnail_metadata
        )

        result["thumbnail_path"] = (
            thumbnail_metadata.get(
                "thumbnail_path"
            )
        )

        result["thumbnail_width"] = (
            thumbnail_metadata.get(
                "thumbnail_width"
            )
        )

        result["thumbnail_height"] = (
            thumbnail_metadata.get(
                "thumbnail_height"
            )
        )

        result["thumbnail_mime_type"] = (
            thumbnail_metadata.get(
                "thumbnail_mime_type"
            )
        )

        result["thumbnail_size_bytes"] = (
            thumbnail_metadata.get(
                "thumbnail_size_bytes"
            )
        )

    def _generate_preview(
        self,
        *,
        file_path: Path,
        sha256: Any,
        warnings: list[str],
    ) -> dict[str, Any] | None:
        """
        Generate a display-compatible image preview.

        Failure does not interrupt image import.
        """

        try:

            return (
                self.preview_generator
                .generate(
                    image_path=file_path,
                    sha256=(
                        str(
                            sha256
                        )
                        if sha256
                        else None
                    ),
                )
            )

        except Exception as error:

            warnings.append(
                "Preview generation failed: "
                f"{error}"
            )

            return None

    @staticmethod
    def _attach_preview_metadata(
        *,
        result: dict[str, Any],
        preview_metadata: (
            dict[str, Any] | None
        ),
    ) -> None:
        """
        Add normalized preview fields to processing result.
        """

        if preview_metadata is None:

            result["preview"] = None

            result["preview_path"] = None

            return

        result["preview"] = (
            preview_metadata
        )

        result["preview_path"] = (
            preview_metadata.get(
                "preview_path"
            )
        )

        result["preview_width"] = (
            preview_metadata.get(
                "preview_width"
            )
        )

        result["preview_height"] = (
            preview_metadata.get(
                "preview_height"
            )
        )

        result["preview_mime_type"] = (
            preview_metadata.get(
                "preview_mime_type"
            )
        )

        result["preview_size_bytes"] = (
            preview_metadata.get(
                "preview_size_bytes"
            )
        )

    # ==========================================================
    # EXIF
    # ==========================================================

    def _extract_exif(
        self,
        *,
        file_path: Path,
        warnings: list[str],
    ) -> dict[str, Any]:
        """
        Extract EXIF, XMP, IPTC and related metadata.

        ExifTool absence or failure does not interrupt import.
        """

        try:

            exif_result = (
                self.exif_extractor.extract(
                    file_path
                )
            )

        except Exception as error:

            warnings.append(
                "ExifTool extraction failed: "
                f"{error}"
            )

            return {
                "status": "failed",
                "available": (
                    self.exif_extractor
                    .is_available()
                ),
                "executable": (
                    str(
                        self.exif_extractor
                        .executable_path
                    )
                    if (
                        self.exif_extractor
                        .executable_path
                    )
                    else None
                ),
                "normalized": {},
                "raw": {},
                "warnings": [],
                "errors": [
                    str(
                        error
                    )
                ],
            }

        exif_warnings = exif_result.get(
            "warnings",
            [],
        )

        if isinstance(
            exif_warnings,
            list,
        ):

            for warning in exif_warnings:

                normalized_warning = str(
                    warning
                ).strip()

                if normalized_warning:

                    warnings.append(
                        "ExifTool: "
                        f"{normalized_warning}"
                    )

        exif_errors = exif_result.get(
            "errors",
            [],
        )

        if isinstance(
            exif_errors,
            list,
        ):

            for error in exif_errors:

                normalized_error = str(
                    error
                ).strip()

                if normalized_error:

                    warnings.append(
                        "ExifTool error: "
                        f"{normalized_error}"
                    )

        return exif_result

    @staticmethod
    def _attach_normalized_exif_fields(
        *,
        result: dict[str, Any],
        exif_metadata: dict[str, Any],
    ) -> None:
        """
        Copy frequently used EXIF values to convenient top-level fields.

        Complete metadata remains available inside result["exif"].
        """

        normalized = exif_metadata.get(
            "normalized"
        )

        if not isinstance(
            normalized,
            dict,
        ):

            normalized = {}

        camera = normalized.get(
            "camera"
        )

        if not isinstance(
            camera,
            dict,
        ):

            camera = {}

        timestamps = normalized.get(
            "timestamps"
        )

        if not isinstance(
            timestamps,
            dict,
        ):

            timestamps = {}

        gps = normalized.get(
            "gps"
        )

        if not isinstance(
            gps,
            dict,
        ):

            gps = {}

        capture = normalized.get(
            "capture"
        )

        if not isinstance(
            capture,
            dict,
        ):

            capture = {}

        authorship = normalized.get(
            "authorship"
        )

        if not isinstance(
            authorship,
            dict,
        ):

            authorship = {}

        result["exif_available"] = bool(
            exif_metadata.get(
                "available",
                False,
            )
        )

        result["exif_status"] = str(
            exif_metadata.get(
                "status"
            )
            or "unknown"
        )

        result["camera_make"] = camera.get(
            "make"
        )

        result["camera_model"] = camera.get(
            "model"
        )

        result["lens_model"] = camera.get(
            "lens_model"
        )

        result["software"] = normalized.get(
            "software"
        )

        result["date_taken"] = timestamps.get(
            "date_taken"
        )

        result["metadata_modify_date"] = (
            timestamps.get(
                "modify_date"
            )
        )

        result["gps"] = gps

        result["gps_available"] = bool(
            gps.get(
                "available",
                False,
            )
        )

        result["gps_latitude"] = gps.get(
            "latitude"
        )

        result["gps_longitude"] = gps.get(
            "longitude"
        )

        result["gps_altitude"] = gps.get(
            "altitude"
        )

        result["iso"] = capture.get(
            "iso"
        )

        result["exposure_time"] = capture.get(
            "exposure_time"
        )

        result["aperture"] = capture.get(
            "aperture"
        )

        result["focal_length"] = capture.get(
            "focal_length"
        )

        result["metadata_orientation"] = (
            capture.get(
                "orientation"
            )
        )

        result["artist"] = authorship.get(
            "artist"
        )

        result["copyright"] = (
            authorship.get(
                "copyright"
            )
        )

        result["image_description"] = (
            normalized.get(
                "description"
            )
        )

        result["keywords"] = (
            normalized.get(
                "keywords",
                [],
            )
        )

        result["editing_software_detected"] = bool(
            normalized.get(
                "editing_software_detected",
                False,
            )
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return image processor information.
        """

        return {
            "type": "image_processor",
            "supported_extensions": sorted(
                self.SUPPORTED_EXTENSIONS
            ),
            "file_processor": (
                self.file_processor
                .__class__
                .__name__
            ),
            "metadata_extractor": (
                self.metadata_extractor
                .metadata()
            ),
            "thumbnail_generator": (
                self.thumbnail_generator
                .metadata()
            ),
            "preview_generator": (
                self.preview_generator
                .metadata()
            ),
            "exif_extractor": (
                self.exif_extractor
                .metadata()
            ),
            "pipeline": [
                "file_metadata",
                "image_metadata",
                "thumbnail",
                "preview",
                "exif",
            ],
        }