from app.infrastructure.open_web.common_crawl_metadata_client import CommonCrawlMetadataClient
class PF:
    def latest_index(self,**k):raise TimeoutError("down")
    def query(self,**k):raise TimeoutError("down")
class PO:
    def latest_index(self,**k):return {"id":"CC-MAIN-2099-01","cdx-api":"https://index.test/CC-MAIN-2099-01-index"}
    def query(self,**k):return [{"url":"https://example.com/"}]
class R:
    def __init__(self):self.calls=[]
    def query(self,**k):self.calls.append(k);return [{"url":k["url_pattern"]}]
def test_primary_success(tmp_path):
    r=R();s=tmp_path/"s.json";c=CommonCrawlMetadataClient(primary=PO(),raw_index=r,state_path=s);i=c.latest_index(timeout=5);assert c.query(cdx_api=i["cdx-api"],url_pattern="https://example.com/",limit=5,timeout=5);assert not r.calls
def test_fallback(tmp_path):
    r=R();c=CommonCrawlMetadataClient(primary=PF(),raw_index=r,state_path=tmp_path/"s.json");i=c.latest_index(timeout=5);assert i["metadata_fallback"]=="raw_zipnum";assert c.query(cdx_api=i["cdx-api"],url_pattern="https://example.com/",limit=5,timeout=5);assert r.calls[0]["crawl_id"]=="CC-MAIN-2026-34"
