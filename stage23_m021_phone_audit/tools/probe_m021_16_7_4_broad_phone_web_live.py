from __future__ import annotations

import sys

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: probe_m021_16_7_4_broad_phone_web_live.py +380XXXXXXXXX")
        return 2

    target = sys.argv[1].strip()
    provider = SearxngPhoneExactOpenWebProvider()

    result = provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value=target,
            limit=20,
            timeout=30,
        )
    )

    print("=" * 76)
    print("BROAD PHONE WEB LIVE PROBE")
    print("=" * 76)
    print("target:", target)
    print("status:", result.status)
    print("error:", result.error)
    print("documents:", result.total_documents)
    print("metadata:", result.metadata)

    for index, document in enumerate(result.documents, start=1):
        print()
        print("--- VERIFIED DOCUMENT", index, "---")
        print("url:", document.url)
        print("title:", document.title)
        print(
            "exact_phone_verified:",
            document.metadata.get("exact_phone_verified"),
        )
        print(
            "candidate_engine:",
            document.metadata.get("candidate_engine"),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
