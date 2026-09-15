from __future__ import annotations

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)

TARGET = "+380632874404"

provider = TargetedPhonePublicSourcesProvider(
    max_candidates=60,
)

intel = provider.phone_service.analyze(TARGET)
plans = provider._build_query_plans(intel)

candidates = provider._discover_candidates(
    plans,
    limit=30,
    timeout=30,
)

target_sets = provider._target_digit_sets(
    intel
)

print("=" * 88)
print("M021.16.7.5.1 CANDIDATE VERIFICATION DIAGNOSTIC")
print("=" * 88)
print("candidates:", len(candidates))

verified = 0
rejected = 0
failed = 0

for i, candidate in enumerate(
    candidates,
    start=1,
):
    url = str(
        candidate.get("url") or ""
    ).strip()

    print()
    print("-" * 88)
    print(i, url)
    print(
        "engine:",
        candidate.get("engine"),
    )
    print(
        "query:",
        candidate.get("_phone_query"),
    )

    result = provider.live_web.search(
        OpenWebQuery(
            target_type=OsintTargetType.URL,
            value=url,
            limit=1,
            timeout=30,
        )
    )

    print("status:", result.status)
    print("error:", result.error)

    if (
        not result.usable
        or not result.documents
    ):
        failed += 1
        continue

    document = result.documents[0]

    print(
        "content_type:",
        document.content_type,
    )
    print(
        "text_length:",
        len(document.extraction_text),
    )

    match = provider._matching_phone_digits(
        document.extraction_text,
        target_sets,
    )

    print("exact_match:", match)

    if match:
        verified += 1
    else:
        rejected += 1

print()
print("=" * 88)
print("SUMMARY")
print("=" * 88)
print("verified:", verified)
print("rejected:", rejected)
print("failed:", failed)
