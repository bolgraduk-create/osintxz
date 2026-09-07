"""
Image processing components.

Contains specialized processors and extractors
used by the image-processing pipeline.

Components in this package do not:

- access the database
- commit transactions
- modify original evidence files
- interact with desktop widgets
"""

from pillow_heif import (
    register_heif_opener,
)


register_heif_opener(
    thumbnails=False,
)


from app.processing.images.image_exif_extractor import (
    ImageExifExtractor,
)

from app.processing.images.image_metadata_extractor import (
    ImageMetadataExtractor,
)

from app.processing.images.image_preview_generator import (
    ImagePreviewGenerator,
)

from app.processing.images.image_thumbnail_generator import (
    ImageThumbnailGenerator,
)


__all__ = [
    "ImageExifExtractor",
    "ImageMetadataExtractor",
    "ImagePreviewGenerator",
    "ImageThumbnailGenerator",
]