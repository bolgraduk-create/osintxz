"""
Metadata extraction service.

Extracts technical metadata
from investigation artifacts.
"""

from __future__ import annotations

from pathlib import Path



class MetadataService:
    """
    Service for extracting metadata.
    """



    def extract_basic_metadata(
        self,
        file_path: str,
    ) -> dict:
        """
        Extract basic file metadata.
        """

        path = Path(
            file_path
        )


        return {
            "filename": path.name,

            "extension": path.suffix.lower(),

            "size": path.stat().st_size,
        }