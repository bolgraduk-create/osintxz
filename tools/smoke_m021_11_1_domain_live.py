from app.infrastructure.open_web.common_crawl_client import CommonCrawlHttpClient
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

def main():
    provider = CommonCrawlOpenWebProvider(CommonCrawlHttpClient(max_attempts=2, backoff_seconds=1.0))
    total = 0
    for domain in ["example.com", "commoncrawl.org"]:
        result = provider.search(OpenWebQuery(OsintTargetType.DOMAIN, domain, limit=5, timeout=15))
        print()
        print("DOMAIN:", domain)
        print("Status:", result.status.value)
        print("Crawl:", result.metadata.get("crawl_id"))
        print("Strategy:", result.metadata.get("query_strategy"))
        print("Documents:", len(result.documents))
        if result.error:
            print("Error:", result.error)
        for doc in result.documents:
            print("-", doc.url, "[" + str(doc.captured_at) + "]")
        total += len(result.documents)
    print()
    print("TOTAL DOMAIN DOCUMENTS:", total)
    return 0 if total > 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
