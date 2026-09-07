import gzip,json
from app.infrastructure.open_web.common_crawl_raw_index import CommonCrawlRawIndexClient,ZipNumBlock
def test_surt():assert CommonCrawlRawIndexClient._surt_key("https://example.com/")=="com,example)/"
def test_parse():assert CommonCrawlRawIndexClient._parse_cluster_line("com,example)/ 20260807100000 cdx-00123.gz 1000 200000 42")==ZipNumBlock("com,example)/","20260807100000","cdx-00123.gz",1000,200000,42)
def test_query(monkeypatch):
    c=CommonCrawlRawIndexClient();monkeypatch.setattr(c,"_find_block",lambda **k:ZipNumBlock("com,example)/","x","cdx-00123.gz",1000,500,42));line="com,example)/ 20260807104456 "+json.dumps({"url":"https://example.com/","filename":"crawl-data/x.warc.gz","offset":"10","length":"20"})+"\n";payload=gzip.compress(line.encode());monkeypatch.setattr(c,"_range_get",lambda *a,**k:payload);rows=c.query(crawl_id="CC-MAIN-2026-34",url_pattern="https://example.com/",limit=5,timeout=5);assert rows[0]["filename"]=="crawl-data/x.warc.gz"
