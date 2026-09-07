from pathlib import Path
PATH=Path("app/core/service_container.py")
IMPORTS='\nfrom app.infrastructure.open_web.common_crawl_metadata_client import (\n    CommonCrawlMetadataClient,\n)\nfrom app.infrastructure.open_web.common_crawl_raw_index import (\n    CommonCrawlRawIndexClient,\n)\n\n'
WIRING='\n        self.common_crawl_raw_index_client = (\n            CommonCrawlRawIndexClient()\n        )\n        self.common_crawl_metadata_client = (\n            CommonCrawlMetadataClient(\n                primary=self.common_crawl_http_client,\n                raw_index=self.common_crawl_raw_index_client,\n            )\n        )\n\n'
def main():
    if not PATH.is_file():print(f"[FAIL] Missing {PATH}");return 1
    original=PATH.read_text(encoding="utf-8"); text=original
    if "from app.infrastructure.open_web.common_crawl_metadata_client import" not in text:
        anchor="class ServiceContainer:"
        if anchor not in text:print("[FAIL] ServiceContainer class anchor not found.");return 1
        text=text.replace(anchor,IMPORTS+anchor,1)
    if "self.common_crawl_metadata_client =" not in text:
        anchor="        self.common_crawl_open_web_provider = (\n"
        if anchor not in text:print("[FAIL] Common Crawl provider wiring anchor not found.");return 1
        text=text.replace(anchor,WIRING+anchor,1)
    pos=text.find("self.common_crawl_open_web_provider ="); tail=text[pos:pos+1200]
    if "self.common_crawl_metadata_client" not in tail:
        old="                client=(\n                    self.common_crawl_http_client\n                ),\n"; new="                client=(\n                    self.common_crawl_metadata_client\n                ),\n"
        if old not in tail:print("[FAIL] Existing provider client anchor not found.");return 1
        tail=tail.replace(old,new,1); text=text[:pos]+tail+text[pos+1200:]
    if not all([text.count("self.common_crawl_raw_index_client =")==1,text.count("self.common_crawl_metadata_client =")==1,text.count("self.common_crawl_open_web_provider =")==1,text.count("self.open_web_provider_registry =")==1,text.count("self.osint_pipeline =")==1]):
        print("[FAIL] Singleton guard failed.");return 1
    compile(text,str(PATH),"exec"); backup=PATH.with_suffix(".py.m021_12_1_backup")
    if text!=original and not backup.exists():backup.write_text(original,encoding="utf-8")
    PATH.write_text(text,encoding="utf-8");print("[PASS] M021.12.1 raw ZipNum metadata fallback wired.");print("[PASS] Common Crawl provider now uses resilient metadata client.");print(f"[INFO] Backup: {backup}");return 0
if __name__=="__main__":raise SystemExit(main())
