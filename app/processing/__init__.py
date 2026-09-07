"""
Processing layer.

Processors transform external data
into application-ready structures.

They do not directly access database.
"""

from pillow_heif import (
    register_heif_opener,
)


register_heif_opener(
    thumbnails=False,
)

from app.processing.base_processor import (
    BaseProcessor,
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

from app.processing.audio_processor import (
    AudioProcessor,
)

from app.processing.document_processor import (
    DocumentProcessor,
)

from app.processing.message_processor import (
    MessageProcessor,
)

from app.processing.file_processing_router import (
    FileProcessingRouter,
)


__all__ = [
    "BaseProcessor",
    "FileProcessor",
    "ImageProcessor",
    "VideoProcessor",
    "AudioProcessor",
    "DocumentProcessor",
    "MessageProcessor",
    "FileProcessingRouter",
]