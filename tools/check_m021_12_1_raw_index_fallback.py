from pathlib import Path
import inspect
from app.infrastructure.open_web.common_crawl_metadata_client import CommonCrawlMetadataClient
from app.infrastructure.open_web.common_crawl_raw_index import CommonCrawlRawIndexClient
def main():
    r=inspect.getsource(CommonCrawlRawIndexClient);m=inspect.getsource(CommonCrawlMetadataClient);t=Path("app/core/service_container.py").read_text();checks=[("data host","data.commoncrawl.org" in r),("cluster range","cluster.idx" in r and "Range" in r),("bounded probes","max_cluster_probes" in r),("bounded block","max_cdx_block_bytes" in r),("fallback","raw_index.query" in m),("one raw client",t.count("self.common_crawl_raw_index_client =")==1),("one metadata client",t.count("self.common_crawl_metadata_client =")==1),("single pipeline",t.count("self.osint_pipeline =")==1)];bad=False
    for label,ok in checks:print(f"[{'PASS' if ok else 'FAIL'}] {label}");bad|=not ok
    print("\nRESULT:","FAIL" if bad else "PASS");return 1 if bad else 0
if __name__=="__main__":raise SystemExit(main())
