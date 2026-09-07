from app.infrastructure.open_web.common_crawl_client import CommonCrawlHttpClient
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

provider = CommonCrawlOpenWebProvider(
    CommonCrawlHttpClient()
)

targets = [
    (
        OsintTargetType.URL,
        "https://commoncrawl.org/",
    ),
    (
        OsintTargetType.URL,
        "https://example.com/",
    ),
    (
        OsintTargetType.DOMAIN,
        "commoncrawl.org",
    ),
    (
        OsintTargetType.DOMAIN,
        "example.com",
    ),
]

print("=" * 72)
print("M021.11 LIVE MULTI-TARGET DIAGNOSTIC")
print("=" * 72)

total_documents = 0

for target_type, value in targets:
    print(
        f"\nTARGET: {target_type.value} "
        f"{value}"
    )

    result = provider.search(
        OpenWebQuery(
            target_type=target_type,
            value=value,
            limit=5,
            timeout=20,
        )
    )

    print(
        f"Status: {result.status.value}"
    )
    print(
        f"Crawl: "
        f"{result.metadata.get('crawl_id')}"
    )
    print(
        f"Documents: "
        f"{len(result.documents)}"
    )

    if result.error:
        print(
            f"Error: {result.error}"
        )

    for document in result.documents[:5]:
        print(
            f"  - {document.url}"
        )
        print(
            f"    captured: "
            f"{document.captured_at}"
        )

    total_documents += len(
        result.documents
    )

print(
    f"\nTOTAL LIVE DOCUMENTS: "
    f"{total_documents}"
)

raise SystemExit(
    0 if total_documents > 0 else 2
)
