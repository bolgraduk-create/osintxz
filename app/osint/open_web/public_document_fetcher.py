from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
from urllib.parse import urljoin, urlsplit
import zipfile
from xml.etree import ElementTree

import httpx

from app.osint.open_web.contracts import OpenWebDocument
from app.osint.open_web.providers.live_web import LiveWebOpenWebProvider


@dataclass(frozen=True, slots=True)
class PublicDocumentFetchOutcome:
    document: OpenWebDocument | None
    error: str | None = None
    content_type: str | None = None
    response_bytes: int = 0
    extraction_kind: str | None = None


class PublicDocumentTextFetcher:
    def __init__(
        self,
        *,
        live_web: LiveWebOpenWebProvider | None = None,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 PublicDocumentFetcher",
        max_response_bytes: int = 12_000_000,
        max_redirects: int = 5,
        max_extracted_chars: int = 2_000_000,
    ) -> None:
        self.live_web = live_web or LiveWebOpenWebProvider()
        self.transport = transport
        self.user_agent = user_agent
        self.max_response_bytes = max(
            1_000_000,
            min(int(max_response_bytes), 20_000_000),
        )
        self.max_redirects = max(0, min(int(max_redirects), 8))
        self.max_extracted_chars = max(
            100_000,
            min(int(max_extracted_chars), 5_000_000),
        )

    def fetch(
        self,
        url: str,
        *,
        timeout: int,
    ) -> PublicDocumentFetchOutcome:
        current = str(url or "").strip()
        if not current:
            return PublicDocumentFetchOutcome(
                document=None,
                error="Document URL is empty.",
            )

        redirects = 0

        while True:
            self.live_web._validate_public_url(current)

            with httpx.Client(
                timeout=httpx.Timeout(float(timeout)),
                follow_redirects=False,
                transport=self.transport,
                verify=self.live_web._tls_context(),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": (
                        "application/pdf,"
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document,"
                        "text/plain,text/csv,application/json,"
                        "application/xml,text/xml,*/*;q=0.2"
                    ),
                },
            ) as client:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            response.raise_for_status()

                        redirects += 1
                        if redirects > self.max_redirects:
                            return PublicDocumentFetchOutcome(
                                document=None,
                                error="Public document redirect limit exceeded.",
                            )

                        current = urljoin(current, location)
                        continue

                    if response.status_code == 404:
                        return PublicDocumentFetchOutcome(
                            document=None,
                            error="Public document returned 404.",
                        )

                    response.raise_for_status()

                    content_type = (
                        response.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .strip()
                        .casefold()
                    )

                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared = int(content_length)
                        except ValueError:
                            declared = None

                        if (
                            declared is not None
                            and declared > self.max_response_bytes
                        ):
                            return PublicDocumentFetchOutcome(
                                document=None,
                                error=(
                                    "Public document exceeds bounded "
                                    "Content-Length limit."
                                ),
                                content_type=content_type or None,
                            )

                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        if len(body) + len(chunk) > self.max_response_bytes:
                            return PublicDocumentFetchOutcome(
                                document=None,
                                error=(
                                    "Public document exceeded bounded "
                                    "download limit."
                                ),
                                content_type=content_type or None,
                                response_bytes=len(body),
                            )
                        body.extend(chunk)

                    final_url = str(response.url)
                    self.live_web._validate_public_url(final_url)

            raw = bytes(body)
            kind = self._detect_kind(
                final_url=final_url,
                content_type=content_type,
                body=raw,
            )

            try:
                text = self._extract(
                    raw,
                    kind=kind,
                    content_type=content_type,
                )
            except Exception as exc:
                return PublicDocumentFetchOutcome(
                    document=None,
                    error=f"Public document text extraction failed: {exc}",
                    content_type=content_type or None,
                    response_bytes=len(raw),
                    extraction_kind=kind,
                )

            text = self._bounded_text(text)

            if not text:
                return PublicDocumentFetchOutcome(
                    document=None,
                    error=(
                        "Public document contains no extractable text. "
                        "It may be scanned/image-only or unsupported."
                    ),
                    content_type=content_type or None,
                    response_bytes=len(raw),
                    extraction_kind=kind,
                )

            return PublicDocumentFetchOutcome(
                document=OpenWebDocument(
                    url=final_url,
                    provider="public_document_fetcher",
                    text=text,
                    content_type=content_type or None,
                    confidence=0.88,
                    reliability=0.88,
                    metadata={
                        "document_fetch": True,
                        "original_url": url.strip(),
                        "final_url": final_url,
                        "redirect_count": redirects,
                        "response_bytes": len(raw),
                        "extraction_kind": kind,
                        "bounded_download": True,
                        "max_response_bytes": self.max_response_bytes,
                        "max_extracted_chars": self.max_extracted_chars,
                        "javascript_executed": False,
                        "ocr_used": False,
                        "public_data_only": True,
                    },
                ),
                content_type=content_type or None,
                response_bytes=len(raw),
                extraction_kind=kind,
            )

    @staticmethod
    def _detect_kind(
        *,
        final_url: str,
        content_type: str,
        body: bytes,
    ) -> str:
        path = urlsplit(final_url).path.casefold()

        if (
            content_type in {"application/pdf", "application/x-pdf"}
            or body[:5] == b"%PDF-"
            or path.endswith(".pdf")
        ):
            return "pdf"

        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or path.endswith(".docx")
        ):
            return "docx"

        if (
            content_type.startswith("text/")
            or content_type
            in {
                "application/json",
                "application/xml",
                "application/xhtml+xml",
            }
            or path.endswith((".txt", ".csv", ".json", ".xml"))
        ):
            return "text"

        return "unsupported"

    def _extract(
        self,
        body: bytes,
        *,
        kind: str,
        content_type: str,
    ) -> str:
        if kind == "pdf":
            return self._extract_pdf(body)

        if kind == "docx":
            return self._extract_docx(body)

        if kind == "text":
            return self._decode_text(body)

        raise ValueError("Unsupported public document format.")

    @staticmethod
    def _extract_pdf(body: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "Python package 'pypdf' is required for PDF extraction."
            ) from exc

        reader = PdfReader(BytesIO(body))
        parts: list[str] = []

        for page in reader.pages:
            value = (page.extract_text() or "").strip()
            if value:
                parts.append(value)

        return "\n".join(parts)

    @staticmethod
    def _extract_docx(body: bytes) -> str:
        max_xml_bytes = 4_000_000
        max_total_xml_bytes = 8_000_000
        with zipfile.ZipFile(BytesIO(body)) as archive:
            names = set(archive.namelist())

            targets = [
                name
                for name in (
                    "word/document.xml",
                    "word/footnotes.xml",
                    "word/endnotes.xml",
                    "word/header1.xml",
                    "word/footer1.xml",
                )
                if name in names
            ]

            parts: list[str] = []
            total = 0

            for name in targets:
                info = archive.getinfo(name)
                if info.file_size > max_xml_bytes or info.flag_bits & 1:
                    raise ValueError("DOCX XML exceeds size limit or is encrypted.")
                with archive.open(info) as stream:
                    xml = stream.read(min(max_xml_bytes, max_total_xml_bytes - total) + 1)
                total += len(xml)
                if len(xml) > max_xml_bytes or total > max_total_xml_bytes:
                    raise ValueError("DOCX XML exceeds decompressed-size limit.")
                # OOXML does not require DTDs or entity declarations. Also detect UTF-16/32 forms.
                declaration_text = xml.replace(b"\x00", b"").upper()
                if b"<!DOCTYPE" in declaration_text or b"<!ENTITY" in declaration_text:
                    raise ValueError("DOCX XML declarations are not permitted.")
                root = ElementTree.fromstring(xml)
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        value = node.text.strip()
                        if value:
                            parts.append(value)

            return "\n".join(parts)

    @staticmethod
    def _decode_text(body: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
            try:
                return body.decode(encoding)
            except UnicodeDecodeError:
                continue

        return body.decode("utf-8", errors="replace")

    def _bounded_text(self, value: str) -> str:
        text = re.sub(r"\x00+", "", str(value or "")).strip()

        if len(text) > self.max_extracted_chars:
            text = text[: self.max_extracted_chars]

        return text
