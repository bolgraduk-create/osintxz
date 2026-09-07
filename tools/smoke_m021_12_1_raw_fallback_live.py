from app.infrastructure.open_web.common_crawl_raw_index import CommonCrawlRawIndexClient
def main():
    print("="*72);print("M021.12.1 LIVE RAW ZIPNUM FALLBACK");rows=CommonCrawlRawIndexClient().query(crawl_id="CC-MAIN-2026-34",url_pattern="https://example.com/",limit=5,timeout=20);print("Records:",len(rows))
    for r in rows:print(r.get("url"),r.get("filename"),r.get("offset"),r.get("length"))
    return 0 if rows else 2
if __name__=="__main__":raise SystemExit(main())
