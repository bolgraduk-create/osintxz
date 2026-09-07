from pathlib import Path
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

class Stub:
    def latest_index(self, **kwargs): return {"id": "x", "cdx-api": "https://x.invalid"}
    def query(self, **kwargs): return []

def main():
    p = CommonCrawlOpenWebProvider(Stub())
    text = Path("app/core/service_container.py").read_text(encoding="utf-8")
    checks = [
        ("passive", p.info.passive),
        ("public data only", p.info.public_data_only),
        ("credential free", not p.info.requires_credentials),
        ("automatic enabled", p.info.default_enabled),
        ("provider registered once", text.count("self.common_crawl_open_web_provider =") == 1),
        ("single Open-Web registry", text.count("self.open_web_provider_registry =") == 1),
        ("single OsintPipeline", text.count("self.osint_pipeline =") == 1),
    ]
    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok
    print("\\nPolicy:")
    print("- Common Crawl public CDXJ URL index only.")
    print("- No target-site crawling or WARC body fetching.")
    print("- No login/API key/CAPTCHA/protection bypass.")
    print("- Bounded DOMAIN/URL lookup.")
    print("- No DB migration.")
    print(f"\\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
