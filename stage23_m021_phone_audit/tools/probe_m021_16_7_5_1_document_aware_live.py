from __future__ import annotations

import sys

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: probe_m021_16_7_5_1_document_aware_live.py "
            "+380XXXXXXXXX"
        )
        return 2

    target = sys.argv[1].strip()
    provider = TargetedPhonePublicSourcesProvider(max_candidates=60)

    result = provider.search(
        OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value=target,
            limit=30,
            timeout=45,
        )
    )

    print("=" * 76)
    print("DOCUMENT-AWARE PHONE LIVE PROBE")
    print("=" * 76)
    print("target:", target)
    print("status:", result.status)
    print("error:", result.error)
    print("documents:", result.total_documents)

    metadata = result.metadata or {}
    for key in (
        "query_count",
        "candidate_count",
        "verified_count",
        "rejected_count",
        "candidate_fetch_failures",
    ):
        print(f"{key}:", metadata.get(key))

    for index, document in enumerate(result.documents, start=1):
        print()
        print("--- VERIFIED", index, "---")
        print("url:", document.url)
        print("title:", document.title)
        print("content_type:", document.content_type)
        print(
            "extraction_kind:",
            document.metadata.get("extraction_kind")
            or document.metadata.get("content_extraction_kind"),
        )
        print("source_rule:", document.metadata.get("source_rule"))
        print("source_tier:", document.metadata.get("source_tier"))
        print("verified:", document.metadata.get("exact_phone_verified"))
        print("response_bytes:", document.metadata.get("response_bytes"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
