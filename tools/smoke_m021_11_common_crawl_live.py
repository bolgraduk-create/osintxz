from app.infrastructure.open_web.common_crawl_client import CommonCrawlHttpClient
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

def main():
    result = CommonCrawlOpenWebProvider(CommonCrawlHttpClient()).search(
        OpenWebQuery(
            OsintTargetType.URL,
            "https://commoncrawl.org/get-started",
            limit=5,
            timeout=15,
        )
    )
    print(f"Status: {result.status.value}")
    print(f"Crawl: {result.metadata.get('crawl_id')}")
    print(f"Documents: {len(result.documents)}")
    if result.error:
        print(f"Error: {result.error}")
    for doc in result.documents:
        print(f"- {doc.url} [{doc.captured_at}]")
    return 0 if result.status.value in {"success", "partial"} else 1

if __name__ == "__main__":
    raise SystemExit(main())
