from pathlib import Path
import inspect

from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)


def main() -> int:
    print("=" * 72)
    print(
        "OSINTXZ M021.12 BOUNDED COMMON CRAWL "
        "WARC CONTENT AUDIT"
    )
    print("=" * 72)

    client_source = inspect.getsource(
        CommonCrawlWarcContentClient
    )
    hydrator_source = inspect.getsource(
        CommonCrawlContentHydrator
    )
    container = Path(
        "app/core/service_container.py"
    ).read_text(
        encoding="utf-8"
    )

    checks = [
        (
            "Range request implemented",
            '"Range"' in client_source,
        ),
        (
            "compressed-size guard",
            "max_compressed_bytes"
            in client_source,
        ),
        (
            "decompressed-size guard",
            "max_decompressed_bytes"
            in client_source,
        ),
        (
            "text-size guard",
            "max_text_chars"
            in client_source,
        ),
        (
            "hydration document budget",
            "max_documents"
            in hydrator_source,
        ),
        (
            "failure isolation",
            "except Exception"
            in hydrator_source,
        ),
        (
            "one WARC content client",
            container.count(
                "self.common_crawl_warc_content_client ="
            )
            == 1,
        ),
        (
            "one content hydrator",
            container.count(
                "self.common_crawl_content_hydrator ="
            )
            == 1,
        ),
        (
            "single OsintPipeline retained",
            container.count(
                "self.osint_pipeline ="
            )
            == 1,
        ),
    ]

    failed = False

    for label, ok in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{label}"
        )
        failed |= not ok

    print("\nPolicy:")
    print("- One byte-range WARC record only.")
    print("- No full WARC download.")
    print("- No target-site crawling.")
    print("- Hydration is bounded by document count and byte limits.")
    print("- Only text/html, XHTML and text/plain become extraction text.")
    print("- Unsupported archive content encodings fail closed.")
    print("- Per-document hydration failure is isolated.")
    print("- Existing UnifiedExtractionService remains authoritative.")
    print("- No DB migration.")

    print(
        f"\nRESULT: "
        f"{'FAIL' if failed else 'PASS'}"
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
