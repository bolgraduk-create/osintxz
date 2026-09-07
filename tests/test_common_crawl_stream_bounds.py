import httpx
import pytest

from app.infrastructure.open_web.common_crawl_warc_client import CommonCrawlWarcContentClient


class TrackedStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    def close(self):
        self.closed = True


def fetch(stream, status=206, headers=None):
    client = CommonCrawlWarcContentClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, stream=stream, headers=headers or {})
    ), max_compressed_bytes=10)
    return client.fetch(filename="crawl-data/test.warc.gz", offset=5, length=10)


def test_range_ignored_rejected_before_reading_full_warc():
    stream = TrackedStream([b"full archive"] * 1000)
    with pytest.raises(ValueError, match="206"):
        fetch(stream, status=200)
    assert stream.read_count == 0
    assert stream.closed


@pytest.mark.parametrize("value", ["", "nonsense", "bytes 0-9/100", "bytes 5-14/14", "bytes 5-15/*"])
def test_bad_content_range_rejected_before_body(value):
    stream = TrackedStream([b"0123456789"])
    with pytest.raises(ValueError, match="Content-Range"):
        fetch(stream, headers={"Content-Range": value})
    assert stream.read_count == 0
    assert stream.closed


def test_oversize_stream_aborts_at_first_byte_over_range():
    stream = TrackedStream([b"0123456789", b"x", b"must not read"])
    with pytest.raises(ValueError, match="compressed-size"):
        fetch(stream, headers={"Content-Range": "bytes 5-14/100"})
    assert stream.read_count == 2
    assert stream.closed


def test_truncated_stream_rejected():
    stream = TrackedStream([b"short"])
    with pytest.raises(ValueError, match="Truncated"):
        fetch(stream, headers={"Content-Range": "bytes 5-14/*"})
    assert stream.closed


def test_oversized_declared_length_rejected_before_read():
    stream = TrackedStream([b"0123456789"])
    with pytest.raises(ValueError, match="Content-Length"):
        fetch(stream, headers={"Content-Range": "bytes 5-14/*", "Content-Length": "10000000"})
    assert stream.read_count == 0
    assert stream.closed
