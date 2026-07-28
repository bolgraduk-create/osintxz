"""
Document processor.

Processes document files.

Responsible only for preparing
document information.

Advanced extraction:
- OCR
- embeddings
- AI analysis

will be implemented in later layers.
"""

from __future__ import annotations

from pathlib import Path

from typing import Any

from app.processing.base_processor import (
    BaseProcessor,
)


class DocumentProcessor(
    BaseProcessor,
):
    """
    Processes document files.
    """


    SUPPORTED_TYPES = {
        ".pdf": "pdf",
        ".doc": "doc",
        ".docx": "docx",
        ".txt": "txt",
        ".html": "html",
        ".csv": "csv",
        ".json": "json",
    }


    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Process document file.

        Returns document metadata.
        """


        file_path = Path(data)


        if not file_path.exists():
            raise FileNotFoundError(
                f"Document not found: {file_path}"
            )


        extension = (
            file_path
            .suffix
            .lower()
        )


        document_type = (
            self.SUPPORTED_TYPES.get(
                extension,
                "other",
            )
        )


        return {
            "title": file_path.name,
            "path": str(file_path),
            "extension": extension,
            "document_type": document_type,
            "size_bytes": file_path.stat().st_size,
        }