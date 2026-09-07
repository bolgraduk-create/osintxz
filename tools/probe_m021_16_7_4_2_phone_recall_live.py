from __future__ import annotations

import sys

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: "
            "probe_m021_16_7_4_2_phone_recall_live.py "
            "+380XXXXXXXXX"
        )
        return 2

    target = sys.argv[1].strip()

    provider = SearxngPhoneExactOpenWebProvider(
        max_candidates=40,
    )

    result = provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value=target,
            limit=20,
            timeout=30,
        )
    )

    print("=" * 76)
    print("PHONE RECALL EXPANSION LIVE PROBE")
    print("=" * 76)
    print("target:", target)
    print("status:", result.status)
    print("error:", result.error)
    print("documents:", result.total_documents)

    metadata = result.metadata or {}

    for key in (
        "candidate_queries",
        "candidate_count",
        "verified_count",
        "rejected_without_exact_phone",
        "candidate_fetch_failures",
    ):
        print(f"{key}:", metadata.get(key))

    for index, document in enumerate(
        result.documents,
        start=1,
    ):
        print()
        print("--- VERIFIED", index, "---")
        print("url:", document.url)
        print("title:", document.title)
        print(
            "engine:",
            document.metadata.get(
                "candidate_engine"
            ),
        )
        print(
            "query:",
            document.metadata.get(
                "candidate_query"
            ),
        )
        print(
            "verified:",
            document.metadata.get(
                "exact_phone_verified"
            ),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
