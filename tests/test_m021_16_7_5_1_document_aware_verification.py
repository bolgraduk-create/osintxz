from io import BytesIO
import zipfile

from app.osint.open_web.public_document_fetcher import (
    PublicDocumentTextFetcher,
)


def test_detect_pdf_by_magic():
    fetcher = PublicDocumentTextFetcher()
    assert (
        fetcher._detect_kind(
            final_url="https://example.test/get?id=1",
            content_type="application/octet-stream",
            body=b"%PDF-1.7\n",
        )
        == "pdf"
    )


def test_detect_docx_by_url():
    fetcher = PublicDocumentTextFetcher()
    assert (
        fetcher._detect_kind(
            final_url="https://example.test/a.docx",
            content_type="application/octet-stream",
            body=b"PK",
        )
        == "docx"
    )


def test_docx_text_extraction():
    memory = BytesIO()

    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0"?>'
                '<w:document '
                'xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main">'
                "<w:body><w:p><w:r>"
                "<w:t>Phone +380671234567</w:t>"
                "</w:r></w:p></w:body></w:document>"
            ),
        )

    text = PublicDocumentTextFetcher._extract_docx(memory.getvalue())
    assert "+380671234567" in text


def test_text_is_bounded():
    fetcher = PublicDocumentTextFetcher(
        max_extracted_chars=100_000,
    )

    value = fetcher._bounded_text("x" * 150_000)
    assert len(value) == 100_000
