"""
File processor.

Responsible for basic file inspection.

Does not store data in database.
Returns processed information
for higher application layers.
"""

from __future__ import annotations

import hashlib

from pathlib import Path

from typing import Any

from app.processing.base_processor import (
    BaseProcessor,
)


class FileProcessor(
    BaseProcessor,
):
    """
    Processes files and extracts metadata.
    """


    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Process file.

        Returns:

        - path
        - filename
        - extension
        - size
        - sha256
        """


        file_path = Path(data)


        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )


        return {
            "path": str(file_path),
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "size_bytes": file_path.stat().st_size,
            "sha256": self._calculate_hash(
                file_path
            ),
        }


    def _calculate_hash(
        self,
        file_path: Path,
    ) -> str:
        """
        Calculate SHA256 hash.
        """


        sha256 = hashlib.sha256()


        with file_path.open(
            "rb"
        ) as file:

            for chunk in iter(
                lambda: file.read(8192),
                b"",
            ):

                sha256.update(chunk)


        return sha256.hexdigest()