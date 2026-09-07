from app.infrastructure.open_web.common_crawl_client import (
    CommonCrawlHttpClient,
)
from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebQuery,
)
from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)


def main() -> int:
    provider = CommonCrawlOpenWebProvider(
        CommonCrawlHttpClient(
            max_attempts=2,
            backoff_seconds=1.0,
        )
    )

    result = provider.search(
        OpenWebQuery(
            OsintTargetType.URL,
            "https://example.com/",
            limit=5,
            timeout=15,
        )
    )

    print("=" * 72)
    print(
        "M021.12 LIVE WARC CONTENT SMOKE"
    )
    print("=" * 72)
    print(
        f"Discovery status: "
        f"{result.status.value}"
    )
    print(
        f"Documents: "
        f"{len(result.documents)}"
    )

    if not result.documents:
        print(
            "No Common Crawl document available."
        )
        return 2

    hydrated = CommonCrawlContentHydrator(
        CommonCrawlWarcContentClient(
            max_compressed_bytes=2_000_000,
            max_decompressed_bytes=4_000_000,
            max_text_chars=50_000,
        ),
        max_documents=1,
        timeout=20,
    ).hydrate(
        result.documents[:1]
    )

    print(
        f"Hydrated: "
        f"{hydrated.hydrated}"
    )
    print(
        f"Failed: "
        f"{hydrated.failed}"
    )

    if hydrated.errors:
        print(
            f"Error: "
            f"{hydrated.errors[0]}"
        )

    document = (
        hydrated.documents[0]
    )

    text = (
        document.text
        or ""
    )

    print(
        f"Text chars: "
        f"{len(text)}"
    )
    print(
        f"Content type: "
        f"{document.content_type}"
    )

    if text:
        print(
            "Preview:"
        )
        print(
            text[:500]
        )

    return (
        0
        if hydrated.hydrated > 0
        and len(text) > 0
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
