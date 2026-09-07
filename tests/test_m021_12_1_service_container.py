from pathlib import Path
def test_wiring():
    t=Path("app/core/service_container.py").read_text();assert t.count("self.common_crawl_raw_index_client =")==1;assert t.count("self.common_crawl_metadata_client =")==1;assert t.count("self.common_crawl_open_web_provider =")==1;assert t.count("self.osint_pipeline =")==1;pos=t.index("self.common_crawl_open_web_provider =");assert "self.common_crawl_metadata_client" in t[pos:pos+1200]
