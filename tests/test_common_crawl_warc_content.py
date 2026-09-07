from __future__ import annotations

import gzip

import httpx
import pytest

from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)


def warc_record(
    body: bytes,
    *,
    content_type="text/html; charset=utf-8",
    content_encoding=None,
):
    headers = [
        b"WARC/1.0",
        b"WARC-Type: response",
        b"WARC-Date: 2026-08-07T10:44:56Z",
        b"WARC-Target-URI: https://example.com/",
        b"WARC-Payload-Digest: sha1:ABC",
        b"Content-Type: application/http; msgtype=response",
        b"",
        b"",
    ]

    http_headers = [
        b"HTTP/1.1 200 OK",
        (
            b"Content-Type: "
            + content_type.encode()
        ),
    ]

    if content_encoding:
        http_headers.append(
            (
                b"Content-Encoding: "
                + content_encoding.encode()
            )
        )

    http_headers.extend(
        [
            b"",
            b"",
        ]
    )

    raw = (
        b"\r\n".join(headers)
        + b"\r\n".join(http_headers)
        + body
    )
    return gzip.compress(
        raw
    )


def test_range_request_and_html_text_extraction():
    seen = []

    payload = warc_record(
        (
            b"<html><body>"
            b"Email alice@example.com "
            b"<script>ignore@example.net</script>"
            b"Phone +380501234567"
            b"</body></html>"
        )
    )

    def handler(request):
        seen.append(request)
        return httpx.Response(
            206,
            content=payload,
            headers={"Content-Range": f"bytes 100-{100 + len(payload) - 1}/*"},
        )

    client = CommonCrawlWarcContentClient(
        transport=httpx.MockTransport(
            handler
        )
    )

    result = client.fetch(
        filename="crawl-data/test.warc.gz",
        offset=100,
        length=len(payload),
        timeout=5,
    )

    assert (
        seen[0].headers["Range"]
        == (
            f"bytes=100-"
            f"{100 + len(payload) - 1}"
        )
    )
    assert "alice@example.com" in result.text
    assert "+380501234567" in result.text
    assert "ignore@example.net" not in result.text
    assert result.metadata["bounded"] is True


def test_compressed_length_guard_blocks_request():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            206,
            content=b"x",
        )

    client = CommonCrawlWarcContentClient(
        transport=httpx.MockTransport(
            handler
        ),
        max_compressed_bytes=10,
    )

    with pytest.raises(
        ValueError,
        match="compressed-size",
    ):
        client.fetch(
            filename="x.warc.gz",
            offset=0,
            length=11,
        )

    assert calls == 0


def test_decompressed_size_guard():
    payload = warc_record(
        b"A" * 2000,
        content_type="text/plain",
    )

    client = CommonCrawlWarcContentClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                206,
                content=payload,
                headers={"Content-Range": f"bytes 0-{len(payload) - 1}/*"},
            )
        ),
        max_decompressed_bytes=100,
    )

    with pytest.raises(
        ValueError,
        match="decompressed-size",
    ):
        client.fetch(
            filename="x.warc.gz",
            offset=0,
            length=len(payload),
        )


def test_unsupported_archived_content_encoding_is_rejected():
    payload = warc_record(
        b"encoded",
        content_encoding="br",
    )

    client = CommonCrawlWarcContentClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                206,
                content=payload,
                headers={"Content-Range": f"bytes 0-{len(payload) - 1}/*"},
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="Unsupported archived HTTP content-encoding",
    ):
        client.fetch(
            filename="x.warc.gz",
            offset=0,
            length=len(payload),
        )


def test_text_limit_is_enforced():
    payload = warc_record(
        b"<html><body>"
        + b"A" * 100
        + b"</body></html>"
    )

    client = CommonCrawlWarcContentClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                206,
                content=payload,
                headers={"Content-Range": f"bytes 0-{len(payload) - 1}/*"},
            )
        ),
        max_text_chars=20,
    )

    result = client.fetch(
        filename="x.warc.gz",
        offset=0,
        length=len(payload),
    )

    assert len(result.text) <= 20
