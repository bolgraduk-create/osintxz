from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

class Stub:
    def latest_index(self, **kwargs):
        return {"id": "x", "cdx-api": "https://x.invalid"}
    def query(self, **kwargs):
        return []

def main():
    provider = CommonCrawlOpenWebProvider(Stub())
    probes = provider._probes(OpenWebQuery(OsintTargetType.DOMAIN, "example.com", limit=5))
    checks = [
        ("four exact probes", len(probes) == 4),
        ("no wildcard", all("*" not in item for item in probes)),
        ("automatic eligible", provider.info.automatic_eligible),
    ]
    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed = failed or not ok
    print()
    print("Policy:")
    print("- Exact homepage probes only.")
    print("- No wildcard domain enumeration.")
    print("- Broad enumeration deferred to URL Index.")
    print("- No DB migration.")
    print()
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
