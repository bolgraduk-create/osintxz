from app.infrastructure.open_web.common_crawl_client import (
    CommonCrawlHttpClient,
)
from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)
from app.osint.open_web.contracts import OpenWebDocument


CDX_API = (
    "https://index.commoncrawl.org/"
    "CC-MAIN-2026-34-index"
)

print("=" * 72)
print("M021.12 DIRECT INDEX -> WARC DIAGNOSTIC")
print("=" * 72)

client = CommonCrawlHttpClient(
    max_attempts=2,
    backoff_seconds=1.0,
)

records = client.query(
    cdx_api=CDX_API,
    url_pattern="https://example.com/",
    limit=5,
    timeout=30,
)

print(f"CDX records: {len(records)}")

if not records:
    print("[FAIL] Direct CDX query returned no records.")
    raise SystemExit(2)

for index, record in enumerate(records[:5], 1):
    print(f"\nRECORD {index}")
    print("URL:", record.get("url"))
    print("Timestamp:", record.get("timestamp"))
    print("Status:", record.get("status"))
    print("MIME:", record.get("mime"))
    print("Filename:", record.get("filename"))
    print("Offset:", record.get("offset"))
    print("Length:", record.get("length"))

record = records[0]

document = OpenWebDocument(
    url=record["url"],
    provider="common_crawl",
    captured_at=None,
    content_type=(
        record.get("mime-detected")
        or record.get("mime")
    ),
    confidence=0.85,
    reliability=0.90,
    metadata={
        "crawl_id": "CC-MAIN-2026-34",
        "warc_filename": record.get("filename"),
        "warc_offset": record.get("offset"),
        "warc_length": record.get("length"),
        "timestamp": record.get("timestamp"),
        "status": record.get("status"),
    },
)

print("\n" + "=" * 72)
print("WARC RANGE FETCH")
print("=" * 72)

hydrator = CommonCrawlContentHydrator(
    CommonCrawlWarcContentClient(
        max_compressed_bytes=2_000_000,
        max_decompressed_bytes=4_000_000,
        max_text_chars=50_000,
    ),
    max_documents=1,
    timeout=30,
)

result = hydrator.hydrate(
    [document]
)

print("Hydrated:", result.hydrated)
print("Failed:", result.failed)
print("Skipped:", result.skipped)
print("Errors:", result.errors)

hydrated = result.documents[0]
text = hydrated.text or ""

print("Content type:", hydrated.content_type)
print("Text chars:", len(text))
print(
    "Hydration metadata:",
    hydrated.metadata.get("content_hydration"),
)

if text:
    print("\nPREVIEW:")
    print(text[:1000])

raise SystemExit(
    0
    if result.hydrated == 1 and len(text) > 0
    else 3
)
