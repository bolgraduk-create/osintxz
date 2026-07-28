"""
Document collector.

Extracts text from documents.

Supported formats:

- TXT
- PDF
- DOCX
"""

from __future__ import annotations


from pathlib import Path


from app.collection.base import (
    BaseCollector,
)


from app.collection.models import (
    CollectedData,
)


from pypdf import PdfReader


from docx import Document



class DocumentCollector(
    BaseCollector
):
    """
    Collector for documents.
    """



    def collect(
        self,
        source: str | Path,
    ) -> CollectedData:
        """
        Extract document content.
        """

        path = Path(
            source
        )


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        extension = (
            path.suffix.lower()
        )


        if extension == ".txt":

            content = (
                path.read_text(
                    encoding="utf-8"
                )
            )


        elif extension == ".pdf":

            content = (
                self._read_pdf(
                    path
                )
            )


        elif extension == ".docx":

            content = (
                self._read_docx(
                    path
                )
            )


        else:

            raise ValueError(
                f"Unsupported format: {extension}"
            )



        metadata = {

            "filename":
                path.name,


            "extension":
                extension,


            "characters":
                len(content),

        }



        return CollectedData(

            source="document",

            content=content,

            metadata=metadata,

        )



    # ==========================================================
    # Readers
    # ==========================================================


    def _read_pdf(
        self,
        path: Path,
    ) -> str:

        reader = PdfReader(
            str(path)
        )


        pages = []


        for page in reader.pages:

            text = (
                page.extract_text()
                or ""
            )

            pages.append(
                text
            )


        return "\n".join(
            pages
        )



    def _read_docx(
        self,
        path: Path,
    ) -> str:

        document = Document(
            str(path)
        )


        paragraphs = [

            paragraph.text

            for paragraph
            in document.paragraphs

        ]


        return "\n".join(
            paragraphs
        )