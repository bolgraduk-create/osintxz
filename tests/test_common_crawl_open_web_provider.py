from __future__ import annotations
import json
import httpx

from app.infrastructure.open_web.common_crawl_client import CommonCrawlHttpClient
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery, OpenWebStatus
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

class Stub:
    def __init__(self, records=None, error=None):
        self.records = list(records or [])
        self.error = error
        self.calls = []
    def latest_index(self, *, timeout=30):
        if self.error: raise self.error
        return {"id": "CC-MAIN-X", "cdx-api": "https://index.test/x"}
    def recent_indexes(self, *, limit=3, timeout=30):
        return [self.latest_index(timeout=timeout)]
    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self.records[:kwargs["limit"]]

def rec(url, timestamp="20260820120000", status="200"):
    return {"url": url, "timestamp": timestamp, "status": status, "mime": "text/html", "mime-detected": "text/html"}

def test_policy_and_targets():
    p = CommonCrawlOpenWebProvider(Stub())
    assert p.info.automatic_eligible
    assert p.supports(OpenWebQuery(OsintTargetType.DOMAIN, "example.org"))
    assert p.supports(OpenWebQuery(OsintTargetType.URL, "https://example.org/a"))
    assert not p.supports(OpenWebQuery(OsintTargetType.EMAIL, "a@example.org"))

def test_exact_url_query():
    s = Stub([rec("https://example.org/a")])
    r = CommonCrawlOpenWebProvider(s).search(OpenWebQuery(OsintTargetType.URL, "https://example.org/a", limit=5))
    assert r.status is OpenWebStatus.SUCCESS
    assert s.calls[0]["url_pattern"] == "https://example.org/a"
    assert r.documents[0].url == "https://example.org/a"

def test_domain_uses_bounded_exact_homepage_probes():
    s = Stub([])
    result = CommonCrawlOpenWebProvider(s).search(
        OpenWebQuery(OsintTargetType.DOMAIN, "example.org", limit=10)
    )
    assert result.status is OpenWebStatus.SUCCESS
    assert [c["url_pattern"] for c in s.calls] == [
        "https://example.org/",
        "http://example.org/",
        "https://www.example.org/",
        "http://www.example.org/",
    ]
    assert all("*" not in c["url_pattern"] for c in s.calls)

def test_duplicate_capture_keeps_newest():
    s = Stub([
        rec("https://example.org/a", "20260801000000"),
        rec("https://example.org/a", "20260820000000"),
    ])
    r = CommonCrawlOpenWebProvider(s).search(OpenWebQuery(OsintTargetType.URL, "https://example.org/a"))
    assert len(r.documents) == 1
    assert r.documents[0].captured_at == "2026-08-20T00:00:00Z"

def test_failure_is_isolated():
    r = CommonCrawlOpenWebProvider(Stub(error=RuntimeError("offline"))).search(OpenWebQuery(OsintTargetType.DOMAIN, "example.org"))
    assert r.status is OpenWebStatus.FAILED
    assert r.metadata["failure_isolated"] is True

def test_http_client_ndjson_and_collinfo():
    def handler(request):
        if str(request.url) == CommonCrawlHttpClient.COLLINFO_URL:
            return httpx.Response(200, json=[{"id": "CC-MAIN-X", "cdx-api": "https://index.test/x"}])
        return httpx.Response(200, text=json.dumps(rec("https://example.org/a")) + "\n")
    c = CommonCrawlHttpClient(transport=httpx.MockTransport(handler))
    latest = c.latest_index(timeout=5)
    rows = c.query(cdx_api=latest["cdx-api"], url_pattern="example.org/*", limit=5, timeout=5)
    assert latest["id"] == "CC-MAIN-X"
    assert rows[0]["url"] == "https://example.org/a"

def test_http_client_404_means_no_capture():
    c = CommonCrawlHttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    assert c.query(cdx_api="https://index.test/x", url_pattern="missing/*", limit=5, timeout=5) == []
