from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider


class FakeClient:
    def __init__(self):
        self.calls=[]

    def recent_indexes(self, *, limit=4, timeout=30):
        assert limit == 4
        return [
            {"id":"CC-MAIN-2026-34","cdx-api":"https://cc/34"},
            {"id":"CC-MAIN-2026-30","cdx-api":"https://cc/30"},
            {"id":"CC-MAIN-2026-25","cdx-api":"https://cc/25"},
        ]

    def latest_index(self, *, timeout=30):
        return self.recent_indexes(limit=1,timeout=timeout)[0]

    def query(self, *, cdx_api, url_pattern, limit, timeout=30):
        self.calls.append((cdx_api,url_pattern,limit))
        if cdx_api.endswith("/34"):
            return []
        if cdx_api.endswith("/30") and "https://www.example.com/page" == url_pattern:
            return [{
                "url":"https://www.example.com/page",
                "status":"200",
                "timestamp":"20260701120000",
                "mime":"text/html",
                "filename":"crawl-data/x.warc.gz",
                "offset":"10",
                "length":"20",
            }]
        return []


def test_multi_crawl_finds_document_not_in_latest_index():
    client=FakeClient()
    provider=CommonCrawlOpenWebProvider(client=client)

    result=provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.URL,
            value="https://www.example.com/page",
            limit=10,
        )
    )

    assert result.usable
    assert len(result.documents) == 1
    assert result.documents[0].metadata["crawl_id"] == "CC-MAIN-2026-30"
    assert result.metadata["crawl_count"] == 3
    assert result.metadata["query_strategy"] == "bounded_exact_variants_multi_crawl"


def test_multi_crawl_never_uses_wildcard():
    client=FakeClient()
    provider=CommonCrawlOpenWebProvider(client=client)

    provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.URL,
            value="https://www.example.com/page",
            limit=10,
        )
    )

    assert client.calls
    assert all("*" not in pattern for _,pattern,_ in client.calls)


def test_multi_crawl_is_bounded_to_four_indexes():
    class ManyClient(FakeClient):
        def recent_indexes(self, *, limit=4, timeout=30):
            assert limit == 4
            return [
                {"id":f"CC-MAIN-2026-{n:02d}","cdx-api":f"https://cc/{n}"}
                for n in (34,30,25,21)
            ]

    client=ManyClient()
    provider=CommonCrawlOpenWebProvider(client=client)
    result=provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.URL,
            value="https://example.com/",
            limit=10,
        )
    )
    assert result.metadata["crawl_count"] <= 4
