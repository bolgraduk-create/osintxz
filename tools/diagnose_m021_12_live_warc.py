from app.infrastructure.open_web.common_crawl_client import (
    CommonCrawlHttpClient,
)
from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)


provider = CommonCrawlOpenWebProvider(
    CommonCrawlHttpClient(
        max_attempts=2,
        backoff_seconds=1.0,
    )
)

targets = [
    "https://example.com/",
    "https://commoncrawl.org/",
    "http://example.com/",
]

print("=" * 72)
print("M021.12 LIVE DISCOVERY + WARC DIAGNOSTIC")
print("=" * 72)

document = None

for value in targets:
    print(f"\nURL: {value}")

    result = provider.search(
        OpenWebQuery(
            OsintTargetType.URL,
            value,
            limit=5,
            timeout=20,
        )
    )

    print(f"Status: {result.status.value}")
    print(f"Error: {result.error}")
    print(f"Crawl: {result.metadata.get('crawl_id')}")
    print(f"Documents: {len(result.documents)}")

    for item in result.documents[:5]:
        print(f"  - {item.url}")
        print(
            "    WARC:",
            item.metadata.get("warc_filename"),
        )
        print(
            "    OFFSET:",
            item.metadata.get("warc_offset"),
        )
        print(
            "    LENGTH:",
            item.metadata.get("warc_length"),
        )

    if result.documents and document is None:
        document = result.documents[0]


if document is None:
    print("\n[FAIL] Discovery returned no live document.")
    raise SystemExit(2)


print("\n" + "=" * 72)
print("WARC RANGE HYDRATION")
print("=" * 72)

hydrator = CommonCrawlContentHydrator(
    CommonCrawlWarcContentClient(
        max_compressed_bytes=2_000_000,
        max_decompressed_bytes=4_000_000,
        max_text_chars=50_000,
    ),
    max_documents=1,
    timeout=20,
)

hydrated = hydrator.hydrate(
    [document]
)

print(f"Hydrated: {hydrated.hydrated}")
print(f"Failed: {hydrated.failed}")
print(f"Skipped: {hydrated.skipped}")
print(f"Errors: {hydrated.errors}")

hydrated_document = hydrated.documents[0]

text = hydrated_document.text or ""

print(f"Content type: {hydrated_document.content_type}")
print(f"Text chars: {len(text)}")

hydration_meta = (
    hydrated_document.metadata.get(
        "content_hydration"
    )
)

print(f"Hydration metadata: {hydration_meta}")

if text:
    print("\nPreview:")
    print(text[:700])

raise SystemExit(
    0
    if hydrated.hydrated > 0 and len(text) > 0
    else 3
)
