from __future__ import annotations

from app.osint.open_web.public_document_fetcher import (
    PublicDocumentTextFetcher,
)
from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)


def main() -> int:
    print("=" * 76)
    print("M021.16.7.5.1 DOCUMENT-AWARE VERIFICATION AUDIT")
    print("=" * 76)

    provider = TargetedPhonePublicSourcesProvider()

    checks = [
        (
            "document fetcher wired",
            isinstance(
                provider.document_fetcher,
                PublicDocumentTextFetcher,
            ),
        ),
        (
            "document limit bounded",
            1_000_000
            <= provider.document_fetcher.max_response_bytes
            <= 20_000_000,
        ),
        (
            "exact phone gate retained",
            provider._matching_phone_digits(
                "Phone +380 67 123 45 67",
                {"380671234567"},
            )
            == "380671234567",
        ),
        (
            "neighbor rejected",
            provider._matching_phone_digits(
                "Phone +380 67 123 45 68",
                {"380671234567"},
            )
            is None,
        ),
    ]

    failed = False

    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print("\nRESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
