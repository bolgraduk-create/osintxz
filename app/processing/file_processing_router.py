"""
File processing router.

Selects the appropriate processor
for an imported file.

Responsible for:

- detecting file category
- selecting a specialized processor
- executing basic file inspection
- returning a unified processing result

Does NOT:

- access the database
- commit transactions
- copy files
- execute OCR
- transcribe audio
- run AI analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.processing.audio_processor import (
    AudioProcessor,
)
from app.processing.document_processor import (
    DocumentProcessor,
)
from app.processing.file_processor import (
    FileProcessor,
)
from app.processing.image_processor import (
    ImageProcessor,
)
from app.processing.video_processor import (
    VideoProcessor,
)


class FileProcessingRouter:
    """
    Routes one file to the appropriate processor.
    """

    ARCHIVE_EXTENSIONS = {
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
    }

    def __init__(
        self,
        *,
        file_processor: FileProcessor | None = None,
        image_processor: ImageProcessor | None = None,
        video_processor: VideoProcessor | None = None,
        audio_processor: AudioProcessor | None = None,
        document_processor: DocumentProcessor | None = None,
    ) -> None:

        self.file_processor = (
            file_processor
            or FileProcessor()
        )

        self.image_processor = (
            image_processor
            or ImageProcessor(
                file_processor=self.file_processor
            )
        )

        self.video_processor = (
            video_processor
            or VideoProcessor(
                file_processor=self.file_processor
            )
        )

        self.audio_processor = (
            audio_processor
            or AudioProcessor(
                file_processor=self.file_processor
            )
        )

        self.document_processor = (
            document_processor
            or DocumentProcessor()
        )

    # ==========================================================
    # Routing
    # ==========================================================

    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Select and execute the appropriate processor.
        """

        path = Path(
            data
        )

        extension = (
            path.suffix.lower()
        )

        if (
            extension
            in ImageProcessor.SUPPORTED_EXTENSIONS
        ):

            return self._build_result(
                category="image",
                processor=self.image_processor,
                data=path,
            )

        if (
            extension
            in VideoProcessor.SUPPORTED_EXTENSIONS
        ):

            return self._build_result(
                category="video",
                processor=self.video_processor,
                data=path,
            )

        if (
            extension
            in AudioProcessor.SUPPORTED_EXTENSIONS
        ):

            return self._build_result(
                category="audio",
                processor=self.audio_processor,
                data=path,
            )

        if (
            extension
            in DocumentProcessor.SUPPORTED_TYPES
        ):

            return self._build_result(
                category="document",
                processor=self.document_processor,
                data=path,
            )

        if extension in self.ARCHIVE_EXTENSIONS:

            metadata = (
                self.file_processor.process(
                    path
                )
            )

            return {
                "status": "completed",
                "category": "archive",
                "processor": (
                    self.file_processor
                    .__class__
                    .__name__
                ),
                "metadata": {
                    **metadata,
                    "archive_type": (
                        extension.lstrip(".")
                    ),
                    "supported": True,
                    "processing_status": (
                        "completed"
                    ),
                    "warnings": [],
                },
                "errors": [],
            }

        metadata = (
            self.file_processor.process(
                path
            )
        )

        return {
            "status": "completed",
            "category": "other",
            "processor": (
                self.file_processor
                .__class__
                .__name__
            ),
            "metadata": {
                **metadata,
                "supported": False,
                "processing_status": (
                    "completed"
                ),
                "warnings": [
                    (
                        "No specialized processor "
                        "is registered for this file type."
                    )
                ],
            },
            "errors": [],
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _build_result(
        *,
        category: str,
        processor,
        data: Path,
    ) -> dict[str, Any]:
        """
        Execute a processor and normalize its result.
        """

        try:

            metadata = processor.process(
                data
            )

            return {
                "status": "completed",
                "category": category,
                "processor": (
                    processor
                    .__class__
                    .__name__
                ),
                "metadata": metadata,
                "errors": [],
            }

        except Exception as error:

            return {
                "status": "failed",
                "category": category,
                "processor": (
                    processor
                    .__class__
                    .__name__
                ),
                "metadata": {},
                "errors": [
                    str(
                        error
                    )
                ],
            }

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return router information.
        """

        return {
            "type": (
                "file_processing_router"
            ),
            "processors": {
                "image": (
                    self.image_processor
                    .__class__
                    .__name__
                ),
                "video": (
                    self.video_processor
                    .__class__
                    .__name__
                ),
                "audio": (
                    self.audio_processor
                    .__class__
                    .__name__
                ),
                "document": (
                    self.document_processor
                    .__class__
                    .__name__
                ),
                "fallback": (
                    self.file_processor
                    .__class__
                    .__name__
                ),
            },
        }