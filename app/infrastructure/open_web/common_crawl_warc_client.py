"""Bounded Common Crawl WARC record retrieval and parsing."""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import gzip
import io
import re
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class WarcContent:
    text: str
    content_type: str | None
    http_status: int | None
    metadata: dict[str, Any]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        if tag.lower() in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._skip_depth += 1

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag.lower()
            in {
                "script",
                "style",
                "noscript",
                "svg",
            }
            and self._skip_depth > 0
        ):
            self._skip_depth -= 1

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._skip_depth == 0:
            value = " ".join(
                data.split()
            )
            if value:
                self.parts.append(
                    value
                )


class CommonCrawlWarcContentClient:
    DATA_BASE_URL = (
        "https://data.commoncrawl.org/"
    )

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = "OSINTXZ/1.0 CommonCrawlWarcClient",
        max_compressed_bytes: int = 2_000_000,
        max_decompressed_bytes: int = 4_000_000,
        max_text_chars: int = 300_000,
    ) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self.max_compressed_bytes = max(
            1,
            int(max_compressed_bytes),
        )
        self.max_decompressed_bytes = max(
            1,
            int(max_decompressed_bytes),
        )
        self.max_text_chars = max(
            1,
            int(max_text_chars),
        )

    def fetch(
        self,
        *,
        filename: str,
        offset: int,
        length: int,
        timeout: int = 20,
    ) -> WarcContent:
        safe_filename = str(
            filename or ""
        ).strip().lstrip("/")

        if not safe_filename:
            raise ValueError(
                "WARC filename is required."
            )

        safe_offset = int(
            offset
        )
        safe_length = int(
            length
        )

        if safe_offset < 0:
            raise ValueError(
                "WARC offset must be >= 0."
            )

        if safe_length <= 0:
            raise ValueError(
                "WARC length must be > 0."
            )

        if (
            safe_length
            > self.max_compressed_bytes
        ):
            raise ValueError(
                "WARC record exceeds compressed-size limit."
            )

        end = (
            safe_offset
            + safe_length
            - 1
        )

        url = (
            self.DATA_BASE_URL
            + safe_filename
        )

        with httpx.Client(
            timeout=httpx.Timeout(
                float(timeout)
            ),
            follow_redirects=False,
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": (
                    "application/octet-stream"
                ),
            },
        ) as client:
            with client.stream(
                "GET", url,
                headers={"Range": f"bytes={safe_offset}-{end}",
                         "Accept-Encoding": "identity"},
            ) as response:
                if response.status_code != 206:
                    response.raise_for_status()
                    raise ValueError("WARC Range request requires HTTP 206.")

                match = re.fullmatch(
                    r"bytes (\d+)-(\d+)/(\d+|\*)",
                    response.headers.get("Content-Range", ""),
                )
                if (
                    match is None
                    or int(match[1]) != safe_offset
                    or int(match[2]) != end
                    or (match[3] != "*" and int(match[3]) <= end)
                ):
                    raise ValueError("Invalid WARC Content-Range.")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected WARC transfer Content-Encoding.")
                declared = response.headers.get("Content-Length")
                if declared is not None and (
                    not declared.isdecimal() or int(declared) != safe_length
                ):
                    raise ValueError("WARC Content-Length does not match requested range.")

                compressed = bytearray()
                for chunk in response.iter_bytes(chunk_size=min(65536, safe_length + 1)):
                    if len(compressed) + len(chunk) > safe_length:
                        raise ValueError("Downloaded WARC record exceeds compressed-size range limit.")
                    compressed.extend(chunk)
                if len(compressed) != safe_length:
                    raise ValueError("Truncated WARC range response.")

        raw = self._bounded_gzip_read(
            compressed
        )

        (
            warc_headers,
            http_status,
            http_headers,
            body,
        ) = self._parse_warc_response(
            raw
        )

        body = self._decode_http_body(
            body,
            http_headers,
        )

        content_type = (
            http_headers.get(
                "content-type"
            )
            or warc_headers.get(
                "warc-identified-payload-type"
            )
        )

        text = self._extract_text(
            body,
            content_type,
            http_headers,
        )

        return WarcContent(
            text=text,
            content_type=content_type,
            http_status=http_status,
            metadata={
                "filename": safe_filename,
                "offset": safe_offset,
                "length": safe_length,
                "range": (
                    f"bytes={safe_offset}-{end}"
                ),
                "warc_type": (
                    warc_headers.get(
                        "warc-type"
                    )
                ),
                "warc_target_uri": (
                    warc_headers.get(
                        "warc-target-uri"
                    )
                ),
                "warc_date": (
                    warc_headers.get(
                        "warc-date"
                    )
                ),
                "warc_payload_digest": (
                    warc_headers.get(
                        "warc-payload-digest"
                    )
                ),
                "decompressed_bytes": (
                    len(raw)
                ),
                "payload_bytes": (
                    len(body)
                ),
                "text_chars": (
                    len(text)
                ),
                "bounded": True,
            },
        )

    def _bounded_gzip_read(
        self,
        compressed: bytes,
    ) -> bytes:
        try:
            with gzip.GzipFile(
                fileobj=io.BytesIO(
                    compressed
                ),
                mode="rb",
            ) as stream:
                raw = stream.read(
                    self.max_decompressed_bytes
                    + 1
                )
        except OSError as exc:
            raise ValueError(
                "Invalid gzip WARC record."
            ) from exc

        if (
            len(raw)
            > self.max_decompressed_bytes
        ):
            raise ValueError(
                "WARC record exceeds decompressed-size limit."
            )

        return raw

    @staticmethod
    def _split_headers(
        data: bytes,
    ) -> tuple[bytes, bytes]:
        for marker in (
            b"\r\n\r\n",
            b"\n\n",
        ):
            if marker in data:
                return data.split(
                    marker,
                    1,
                )

        raise ValueError(
            "Header separator not found."
        )

    @classmethod
    def _parse_headers(
        cls,
        block: bytes,
    ) -> dict[str, str]:
        lines = block.decode(
            "iso-8859-1",
            errors="replace",
        ).splitlines()

        result: dict[
            str,
            str,
        ] = {}

        for line in lines[1:]:
            if ":" not in line:
                continue

            key, value = line.split(
                ":",
                1,
            )

            result[
                key.strip().lower()
            ] = value.strip()

        return result

    @classmethod
    def _parse_warc_response(
        cls,
        raw: bytes,
    ) -> tuple[
        dict[str, str],
        int | None,
        dict[str, str],
        bytes,
    ]:
        warc_block, payload = (
            cls._split_headers(
                raw
            )
        )

        if not warc_block.startswith(
            b"WARC/"
        ):
            raise ValueError(
                "Expected WARC response record."
            )

        warc_headers = (
            cls._parse_headers(
                warc_block
            )
        )

        http_block, body = (
            cls._split_headers(
                payload
            )
        )

        lines = http_block.decode(
            "iso-8859-1",
            errors="replace",
        ).splitlines()

        if (
            not lines
            or not lines[0].startswith(
                "HTTP/"
            )
        ):
            raise ValueError(
                "WARC payload is not an HTTP response."
            )

        status = None

        parts = lines[0].split()

        if len(parts) >= 2:
            try:
                status = int(
                    parts[1]
                )
            except ValueError:
                status = None

        http_headers = (
            cls._parse_headers(
                http_block
            )
        )

        return (
            warc_headers,
            status,
            http_headers,
            body,
        )

    def _decode_http_body(
        self,
        body: bytes,
        headers: dict[str, str],
    ) -> bytes:
        encoding = (
            headers.get(
                "content-encoding",
                "",
            )
            .split(",", 1)[0]
            .strip()
            .lower()
        )

        if encoding in {
            "",
            "identity",
        }:
            return body

        if encoding == "gzip":
            try:
                with gzip.GzipFile(
                    fileobj=io.BytesIO(
                        body
                    ),
                    mode="rb",
                ) as stream:
                    decoded = stream.read(
                        self.max_decompressed_bytes
                        + 1
                    )
            except OSError as exc:
                raise ValueError(
                    "Invalid gzip HTTP payload."
                ) from exc

            if (
                len(decoded)
                > self.max_decompressed_bytes
            ):
                raise ValueError(
                    "HTTP payload exceeds decompressed-size limit."
                )

            return decoded

        raise ValueError(
            "Unsupported archived HTTP content-encoding: "
            f"{encoding}"
        )

    def _extract_text(
        self,
        body: bytes,
        content_type: str | None,
        headers: dict[str, str],
    ) -> str:
        media_type = (
            str(
                content_type
                or ""
            )
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if media_type not in {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
        }:
            return ""

        charset = "utf-8"

        raw_content_type = (
            headers.get(
                "content-type",
                "",
            )
        )

        for part in (
            raw_content_type.split(
                ";"
            )[1:]
        ):
            if (
                "=" in part
                and part.split(
                    "=",
                    1,
                )[0].strip().lower()
                == "charset"
            ):
                charset = (
                    part.split(
                        "=",
                        1,
                    )[1]
                    .strip()
                    .strip('"')
                    .strip("'")
                    or "utf-8"
                )

        try:
            decoded = body.decode(
                charset,
                errors="replace",
            )
        except LookupError:
            decoded = body.decode(
                "utf-8",
                errors="replace",
            )

        if media_type == "text/plain":
            text = " ".join(
                decoded.split()
            )
            return text[
                : self.max_text_chars
            ]

        parser = _VisibleTextParser()

        try:
            parser.feed(
                decoded
            )
            parser.close()
        except Exception:
            text = " ".join(
                decoded.split()
            )
        else:
            text = " ".join(
                parser.parts
            )

        return text[
            : self.max_text_chars
        ]
