from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from app.osint.open_web.public_document_fetcher import PublicDocumentTextFetcher


def docx(xml):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def test_compressed_docx_cannot_expand_unbounded_xml():
    payload = docx(b"A" * 4_000_001)
    assert len(payload) < 10000
    with pytest.raises(ValueError, match="size limit"):
        PublicDocumentTextFetcher._extract_docx(payload)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_docx_entity_declarations_rejected(encoding):
    xml = '<!DOCTYPE x [<!ENTITY a "expanded">]><x>&a;</x>'
    with pytest.raises(ValueError, match="declarations"):
        PublicDocumentTextFetcher._extract_docx(docx(xml.encode(encoding)))


def test_docx_embedded_text_still_extracts():
    xml = b'<w:document xmlns:w="urn:word"><w:t>public@example.org</w:t></w:document>'
    assert PublicDocumentTextFetcher._extract_docx(docx(xml)) == "public@example.org"
